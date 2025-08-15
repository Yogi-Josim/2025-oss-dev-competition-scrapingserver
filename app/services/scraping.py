import time
from datetime import datetime, timedelta
# [수정] Selenium 대신 Playwright를 임포트합니다.
from playwright.sync_api import sync_playwright, \
  TimeoutError as PlaywrightTimeoutError
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


# [수정] 각 스레드가 실행할 작업 함수를 Playwright 용으로 변경합니다.
def worker(playwright, task_queue, results, time_cutoff):
  # 각 스레드는 시작할 때 단 한 번만 브라우저를 생성합니다.
  browser = playwright.chromium.launch(headless=True)
  page = browser.new_page()

  while not task_queue.empty():
    try:
      link, gallery_id = task_queue.get(block=False)

      # Playwright를 사용하여 페이지로 이동하고, 댓글이 로드될 때까지 기다립니다.
      page.goto(link, timeout=20000)  # 20초 타임아웃
      page.wait_for_selector(".cmt_box", timeout=5000)  # 댓글 영역 5초 대기

      page_source = page.content()

      result = _scrape_details_with_bs(
          page_source,
          time_cutoff,
          f"dcinside_{gallery_id}",
          page.url
      )
      if result:
        results.append(result)
    except PlaywrightTimeoutError:
      # 댓글 로딩 타임아웃 시, 댓글 없는 페이지로 간주하고 바로 파싱
      print(f"  [정보] 댓글 로딩 시간 초과 (댓글 없는 페이지 가능성): {link}")
      try:
        page_source = page.content()
        result = _scrape_details_with_bs(page_source, time_cutoff,
                                         f"dcinside_{gallery_id}", page.url)
        if result:
          results.append(result)
      except Exception as e_inner:
        print(f"  [오류] 타임아웃 후 '{link}' 처리 중 오류 발생: {e_inner}")
    except Exception as e:
      print(f"  [오류] '{link}' 처리 중 오류 발생: {e}")
    finally:
      task_queue.task_done()

  browser.close()


# [수정] 메인 스크래핑 함수를 Playwright 생산자-소비자 모델로 재설계합니다.
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

  # Playwright는 스레드마다 별도의 인스턴스가 필요합니다.
  with sync_playwright() as p:
    for _ in range(NUM_WORKERS):
      # 각 스레드에 playwright 인스턴스를 전달합니다.
      t = Thread(target=worker,
                 args=(p, task_queue, final_results, time_cutoff))
      t.start()
      threads.append(t)

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
