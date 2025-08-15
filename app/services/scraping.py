import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
# [추가] 명시적 대기를 위해 WebDriverWait와 EC를 다시 임포트합니다.
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
from bs4 import BeautifulSoup
from app.core.config import settings
from queue import Queue
from threading import Thread


def _parse_time(time_str: str) -> datetime:
  try:
    return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
  except ValueError:
    return datetime.min


def _scrape_details_with_bs(page_source: str, time_cutoff: datetime,
    source_community: str, current_url: str):
  try:
    soup = BeautifulSoup(page_source, 'html.parser')

    time_element = soup.select_one(settings.TIME_SELECTOR)
    post_time_str = time_element.get('title') if time_element else ''
    post_time = _parse_time(post_time_str)

    if not post_time or post_time == datetime.min or post_time < time_cutoff:
      return "STOP"

    title_element = soup.select_one(settings.TITLE_SELECTOR)
    title = title_element.text.strip() if title_element else "제목 없음"

    content_element = soup.select_one(settings.CONTENT_SELECTOR)
    content = content_element.text.strip() if content_element else ""

    raw_content = f"{title}\n\n{content}"

    comment_elements = soup.select(settings.COMMENT_LIST_SELECTOR)
    comments = [el.text.strip() for el in comment_elements if el.text.strip()]

    return {
      "source_community": source_community, "source_url": current_url,
      "raw_content": raw_content, "crawled_at": datetime.now().isoformat(),
      "comments": comments,
      "post_time": post_time
    }
  except Exception as e:
    print(f"  [오류] BeautifulSoup 파싱 중 오류: {e}")
    return None


# [수정] 각 스레드가 실행할 작업 함수입니다.
# 최적화된 Selenium-only 방식으로 변경합니다.
def worker(task_queue, results, time_cutoff):
  options = webdriver.ChromeOptions()
  options.add_argument('--headless=new')
  options.add_argument('--no-sandbox')
  options.add_argument('--disable-dev-shm-usage')
  options.add_argument('--disable-gpu')
  options.add_argument("--window-size=1920,1080")
  options.add_argument("--disable-extensions")
  options.add_argument("--disable-setuid-sandbox")

  # [수정] JavaScript는 활성화 상태로 두고, 이미지와 CSS만 비활성화하여
  # 댓글 로딩은 가능하게 하면서 서버 부하를 최소화합니다.
  prefs = {
    "profile.managed_default_content_settings.images": 2,
    "profile.managed_default_content_settings.stylesheets": 2,
  }
  options.add_experimental_option("prefs", prefs)

  options.binary_location = "/usr/bin/chromium"
  service = Service(executable_path="/usr/bin/chromedriver")

  driver = webdriver.Chrome(service=service, options=options)
  driver.set_page_load_timeout(20)  # 타임아웃을 20초로 조절

  while not task_queue.empty():
    try:
      link, gallery_id = task_queue.get(block=False)
      driver.get(link)

      # [수정] 댓글 영역이 로드될 때까지 최대 5초간 명시적으로 기다립니다.
      # 이 부분이 댓글 누락을 방지하는 핵심 로직입니다.
      WebDriverWait(driver, 5).until(
          EC.presence_of_element_located((By.CSS_SELECTOR, ".cmt_box"))
      )

      page_source = driver.page_source

      result = _scrape_details_with_bs(
          page_source,
          time_cutoff,
          f"dcinside_{gallery_id}",
          driver.current_url
      )
      if result:
        results.append(result)
    except TimeoutException:
      # 댓글 로딩을 기다리다 타임아웃이 발생하면, 댓글이 없는 페이지로 간주하고 HTML을 바로 가져옵니다.
      print(f"  [정보] 댓글 로딩 시간 초과 (댓글 없는 페이지 가능성): {link}")
      try:
        page_source = driver.page_source
        result = _scrape_details_with_bs(
            page_source, time_cutoff, f"dcinside_{gallery_id}",
            driver.current_url
        )
        if result:
          results.append(result)
      except Exception as e_inner:
        print(f"  [오류] 타임아웃 후 '{link}' 처리 중 오류 발생: {e_inner}")

    except Exception as e:
      print(f"  [오류] '{link}' 처리 중 오류 발생: {e}")
    finally:
      task_queue.task_done()

  driver.quit()


def run_dcinside_scraper(crawl_hours: int):
  time_cutoff = datetime.now() - timedelta(hours=crawl_hours)

  task_queue = Queue()
  for gallery in settings.GALLERIES_TO_SCRAPE:
    gallery_id, gallery_name = gallery["id"], gallery["name"]
    list_url = f"{settings.BASE_URL}/board/lists/?id={gallery_id}&exception_mode=recommend"
    print(f"--- [ {gallery_name} ] 목록 확인 중 ---")
    try:
      response = requests.get(list_url, headers={'User-Agent': 'Mozilla/5.0'})
      soup = BeautifulSoup(response.text, 'html.parser')
      post_links = [settings.BASE_URL + tag['href'] for row in
                    soup.select(settings.POST_ROW_SELECTOR) if
                    (tag := row.select_one(settings.POST_LINK_SELECTOR))]

      for link in post_links:
        task_queue.put((link, gallery_id))
    except Exception as e:
      print(f"  [오류] {gallery_name} 목록을 가져오는 중 오류 발생: {e}")

  NUM_WORKERS = 4
  final_results = []
  threads = []

  print(
    f"총 {task_queue.qsize()}개의 게시물을 병렬로 스크래핑합니다 (최대 {NUM_WORKERS}개 동시 실행)...")

  for _ in range(NUM_WORKERS):
    t = Thread(target=worker, args=(task_queue, final_results, time_cutoff))
    t.start()
    threads.append(t)
    time.sleep(1)

  task_queue.join()

  for t in threads:
    t.join()

  print(f"[DEBUG] 스크래핑 완료. 결과를 시간순으로 정렬합니다...")
  valid_results = [res for res in final_results if res != "STOP"]
  valid_results.sort(key=lambda x: x.get('post_time', datetime.min),
                     reverse=True)

  for result in valid_results:
    result.pop('post_time', None)

  print(f"[DEBUG] 정렬 완료. 총 {len(valid_results)}개의 유효한 게시물 발견.")
  return valid_results
