import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
# WebDriverWait와 EC는 더 이상 필요하지 않습니다.
import requests
from bs4 import BeautifulSoup
from app.core.config import settings


def _parse_time(time_str: str) -> datetime:
  try:
    return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
  except ValueError:
    return None


# [수정] Selenium은 HTML을 가져오는 역할만 하고, 파싱은 BeautifulSoup이 담당합니다.
# 이 방법이 동적 웹사이트를 스크래핑할 때 가장 안정적입니다.
def _scrape_details_with_bs(page_source: str, time_cutoff: datetime,
    source_community: str, current_url: str):
  try:
    soup = BeautifulSoup(page_source, 'html.parser')

    # BeautifulSoup을 사용하여 요소 찾기
    time_element = soup.select_one(settings.TIME_SELECTOR)
    # DCinside는 title 속성에 전체 날짜/시간이 들어있습니다.
    post_time_str = time_element.get('title') if time_element else ''
    post_time = _parse_time(post_time_str)

    if not post_time or post_time < time_cutoff:
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
      "comments": comments
    }
  except Exception as e:
    print(f"  [오류] BeautifulSoup 파싱 중 오류: {e}")
    return None


def run_dcinside_scraper(crawl_hours: int):
  time_cutoff = datetime.now() - timedelta(hours=crawl_hours)

  options = webdriver.ChromeOptions()
  options.add_argument('--headless=new')
  options.add_argument('--no-sandbox')
  options.add_argument('--disable-dev-shm-usage')
  options.add_argument('--disable-gpu')
  options.add_argument("--window-size=1920,1080")
  options.binary_location = "/usr/bin/chromium"

  service = Service(executable_path="/usr/bin/chromedriver")

  print("[DEBUG] Selenium WebDriver를 생성합니다...")
  driver = webdriver.Chrome(service=service, options=options)
  print("[DEBUG] WebDriver 생성 완료.")

  final_results = []
  try:
    # 페이지 로드 타임아웃은 그대로 유지합니다.
    driver.set_page_load_timeout(30)
    for gallery in settings.GALLERIES_TO_SCRAPE:
      gallery_id, gallery_name = gallery["id"], gallery["name"]
      list_url = f"{settings.BASE_URL}/board/lists/?id={gallery_id}&exception_mode=recommend"
      print(f"--- [ {gallery_name} ] 확인 중 ---")

      # 게시물 목록은 원래대로 requests를 사용합니다. (빠르고 효율적)
      response = requests.get(list_url, headers={'User-Agent': 'Mozilla/5.0'})
      soup = BeautifulSoup(response.text, 'html.parser')
      post_links = [settings.BASE_URL + tag['href'] for row in
                    soup.select(settings.POST_ROW_SELECTOR) if
                    (tag := row.select_one(settings.POST_LINK_SELECTOR))]

      for link in post_links:
        try:
          driver.get(link)
          # [수정] 페이지가 로드된 후, 최종 HTML 소스를 가져옵니다.
          page_source = driver.page_source
        except TimeoutException:
          print(f"  [경고] 페이지 로딩 시간 초과: {link}")
          continue
        except Exception as e:
          print(f"  [경고] 페이지 로딩 중 알 수 없는 오류: {link}, 에러: {e}")
          continue

        # [수정] 가져온 HTML 소스를 새로운 파싱 함수에 전달합니다.
        result = _scrape_details_with_bs(page_source, time_cutoff,
                                         f"dcinside_{gallery_id}",
                                         driver.current_url)
        if result == "STOP":
          break
        elif result:
          final_results.append(result)

  finally:
    print("[DEBUG] 스크래핑 루프 종료. WebDriver를 닫습니다.")
    driver.quit()

  return final_results
