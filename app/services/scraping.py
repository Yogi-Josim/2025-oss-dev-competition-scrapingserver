import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
import requests
from bs4 import BeautifulSoup
from app.core.config import settings
from queue import Queue
# [수정] 각 스레드마다 독립적인 Selenium 드라이버를 관리하기 위해 threading.local을 사용합니다.
from threading import Thread, local

# 각 스레드에 대한 드라이버 인스턴스를 저장할 thread-local 객체
thread_local_storage = local()


def get_selenium_driver():
  """
  현재 스레드에 대한 Selenium WebDriver 인스턴스를 생성하거나 기존 인스턴스를 반환합니다.
  드라이버는 필요할 때만 (requests 실패 시) 생성됩니다.
  """
  driver = getattr(thread_local_storage, 'driver', None)
  if driver is None:
    print(f"  [정보] 스레드를 위한 Selenium 드라이버를 새로 생성합니다...")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-setuid-sandbox")
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    options.binary_location = "/usr/bin/chromium"
    service = Service(executable_path="/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(15)
    setattr(thread_local_storage, 'driver', driver)
  return driver


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


# [수정] 각 스레드가 실행할 작업 함수입니다. 하이브리드 방식을 사용합니다.
def worker(task_queue, results, time_cutoff):
  while not task_queue.empty():
    try:
      link, gallery_id = task_queue.get(block=False)
      page_source = None

      # 1. 가장 빠른 requests로 먼저 시도합니다.
      try:
        response = requests.get(link, headers={'User-Agent': 'Mozilla/5.0'},
                                timeout=10)
        response.raise_for_status()  # 200 OK가 아니면 예외 발생
        page_source = response.text
      except requests.RequestException as e:
        print(f"  [정보] requests 실패: {link}. Selenium으로 재시도합니다. (이유: {e})")
        # requests 실패 시, 비상용으로 Selenium을 사용합니다.
        driver = get_selenium_driver()
        driver.get(link)
        page_source = driver.page_source

      if page_source:
        result = _scrape_details_with_bs(
            page_source,
            time_cutoff,
            f"dcinside_{gallery_id}",
            link  # URL은 원래 링크를 사용
        )
        if result:
          results.append(result)

    except Exception as e:
      print(f"  [오류] '{link}' 처리 중 심각한 오류 발생: {e}")
    finally:
      task_queue.task_done()


def run_dcinside_scraper(crawl_hours: int):
  time_cutoff = datetime.now() - timedelta(hours=crawl_hours)

  task_queue = Queue()
  # 1. 생산자: 모든 링크를 수집합니다.
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

  # 2. 소비자: 스레드들을 생성하고 작업을 시작시킵니다.
  NUM_WORKERS = 4
  final_results = []
  threads = []

  print(
    f"총 {task_queue.qsize()}개의 게시물을 하이브리드 방식으로 스크래핑합니다 (최대 {NUM_WORKERS}개 동시 실행)...")

  for _ in range(NUM_WORKERS):
    t = Thread(target=worker, args=(task_queue, final_results, time_cutoff))
    t.start()
    threads.append(t)

  # 3. 모든 작업이 끝날 때까지 기다립니다.
  task_queue.join()

  # 4. 모든 스레드가 종료될 때까지 기다립니다.
  for t in threads:
    t.join()

  # 5. 스레드에 할당된 모든 드라이버를 종료합니다.
  driver = getattr(thread_local_storage, 'driver', None)
  if driver:
    print("  [정보] 스레드에 사용된 Selenium 드라이버를 종료합니다.")
    driver.quit()
    delattr(thread_local_storage, 'driver')

  # 6. 결과를 시간순으로 정렬합니다.
  print(f"[DEBUG] 스크래핑 완료. 결과를 시간순으로 정렬합니다...")
  valid_results = [res for res in final_results if res != "STOP"]
  valid_results.sort(key=lambda x: x.get('post_time', datetime.min),
                     reverse=True)

  for result in valid_results:
    result.pop('post_time', None)

  print(f"[DEBUG] 정렬 완료. 총 {len(valid_results)}개의 유효한 게시물 발견.")
  return valid_results
