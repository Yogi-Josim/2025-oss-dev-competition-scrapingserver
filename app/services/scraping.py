import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
import requests
from bs4 import BeautifulSoup
from app.core.config import settings
# [수정] 병렬 처리를 위한 라이브러리 변경
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


# [수정] 각 스레드(소비자)가 실행할 작업 함수입니다.
# 큐에서 작업을 가져와 처리하고, 결과는 results 리스트에 추가합니다.
def worker(task_queue, results, time_cutoff):
  # 각 스레드는 시작할 때 단 한 번만 브라우저를 생성합니다.
  options = webdriver.ChromeOptions()
  options.add_argument('--headless=new')
  options.add_argument('--no-sandbox')
  options.add_argument('--disable-dev-shm-usage')
  options.add_argument('--disable-gpu')
  options.add_argument("--window-size=1920,1080")
  options.add_argument("--disable-extensions")
  options.add_argument("--disable-setuid-sandbox")
  options.binary_location = "/usr/bin/chromium"
  service = Service(executable_path="/usr/bin/chromedriver")

  driver = webdriver.Chrome(service=service, options=options)
  driver.set_page_load_timeout(30)

  while not task_queue.empty():
    try:
      link, gallery_id = task_queue.get(block=False)
      driver.get(link)
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
      print(f"  [경고] 페이지 로딩 시간 초과: {link}")
    except Exception as e:
      print(f"  [오류] '{link}' 처리 중 오류 발생: {e}")
    finally:
      # 작업이 끝나면 큐에 완료 신호를 보냅니다.
      task_queue.task_done()

  # 루프가 끝나면 브라우저를 종료합니다.
  driver.quit()


# [수정] 메인 스크래핑 함수를 생산자-소비자 모델로 재설계합니다.
def run_dcinside_scraper(crawl_hours: int):
  time_cutoff = datetime.now() - timedelta(hours=crawl_hours)

  # 1. 생산자: 모든 갤러리에서 스크래핑할 링크를 수집하여 "업무 바구니"(큐)에 넣습니다.
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

  # 2. 소비자: 스레드(직원)들을 생성하고 작업을 시작시킵니다.
  # NUM_WORKERS는 동시에 실행할 브라우저 수입니다.
  NUM_WORKERS = 4
  final_results = []
  threads = []

  print(
    f"총 {task_queue.qsize()}개의 게시물을 병렬로 스크래핑합니다 (최대 {NUM_WORKERS}개 동시 실행)...")

  for _ in range(NUM_WORKERS):
    t = Thread(target=worker, args=(task_queue, final_results, time_cutoff))
    t.start()
    threads.append(t)

  # 3. 모든 작업이 끝날 때까지 기다립니다.
  task_queue.join()

  # 모든 스레드가 종료될 때까지 기다립니다.
  for t in threads:
    t.join()

  # 4. 모든 스크래핑이 끝난 후, 결과를 시간순으로 정렬합니다.
  print(f"[DEBUG] 스크래핑 완료. 결과를 시간순으로 정렬합니다...")
  valid_results = [res for res in final_results if res != "STOP"]
  valid_results.sort(key=lambda x: x.get('post_time', datetime.min),
                     reverse=True)

  # 최종 반환 전, 정렬에 사용된 'post_time' 키를 제거합니다.
  for result in valid_results:
    result.pop('post_time', None)

  print(f"[DEBUG] 정렬 완료. 총 {len(valid_results)}개의 유효한 게시물 발견.")
  return valid_results
