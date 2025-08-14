import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
import requests
from bs4 import BeautifulSoup
from app.core.config import settings
# [추가] 병렬 처리를 위한 concurrent.futures 라이브러리를 임포트합니다.
import concurrent.futures


def _parse_time(time_str: str) -> datetime:
  try:
    return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
  except ValueError:
    # 파싱할 수 없는 시간 형식일 경우, 아주 오래된 시간을 반환하여 정렬 시 맨 뒤로 가도록 합니다.
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
      # [추가] 정렬을 위해 파싱된 시간(datetime 객체)을 결과에 포함시킵니다.
      "post_time": post_time
    }
  except Exception as e:
    print(f"  [오류] BeautifulSoup 파싱 중 오류: {e}")
    return None


# [추가] 각 스레드에서 단일 게시물을 스크래핑하는 작업 함수입니다.
def scrape_single_post(link_info):
  link, gallery_id, time_cutoff = link_info

  # 각 스레드는 독립적인 웹 드라이버 인스턴스를 생성하고 관리해야 합니다.
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

  driver = None
  try:
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    driver.get(link)
    page_source = driver.page_source

    result = _scrape_details_with_bs(
        page_source,
        time_cutoff,
        f"dcinside_{gallery_id}",
        driver.current_url
    )
    return result
  except Exception as e:
    print(f"  [오류] '{link}' 처리 중 오류 발생: {e}")
    return None
  finally:
    if driver:
      driver.quit()


# [수정] 메인 스크래핑 함수를 병렬 처리 방식으로 변경합니다.
def run_dcinside_scraper(crawl_hours: int):
  time_cutoff = datetime.now() - timedelta(hours=crawl_hours)

  all_links_to_scrape = []
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
        all_links_to_scrape.append((link, gallery_id, time_cutoff))
    except Exception as e:
      print(f"  [오류] {gallery_name} 목록을 가져오는 중 오류 발생: {e}")

  final_results = []
  # [수정] 동시 작업 수를 10개에서 4개로 줄여 서버 과부하를 방지합니다.
  # 이 값은 서버 사양에 따라 조절할 수 있습니다.
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    print(f"총 {len(all_links_to_scrape)}개의 게시물을 병렬로 스크래핑합니다 (최대 4개 동시 실행)...")
    results_iterator = executor.map(scrape_single_post, all_links_to_scrape)

    for result in results_iterator:
      if result and result != "STOP":
        final_results.append(result)

  # [추가] 모든 스크래핑이 끝난 후, 'post_time'을 기준으로 최신순(내림차순)으로 정렬합니다.
  print(f"[DEBUG] 스크래핑 완료. 결과를 시간순으로 정렬합니다...")
  final_results.sort(key=lambda x: x.get('post_time', datetime.min),
                     reverse=True)

  # [추가] 최종 반환 전, 정렬에 사용된 'post_time' 키를 제거합니다.
  for result in final_results:
    result.pop('post_time', None)

  print(f"[DEBUG] 정렬 완료. 총 {len(final_results)}개의 유효한 게시물 발견.")
  return final_results
