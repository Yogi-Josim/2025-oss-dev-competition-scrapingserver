import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
import requests
from bs4 import BeautifulSoup
from app.core.config import settings


def _parse_time(time_str: str) -> datetime:
  try:
    return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
  except ValueError:
    return None


def _scrape_details_with_bs(page_source: str, time_cutoff: datetime,
    source_community: str, current_url: str):
  try:
    soup = BeautifulSoup(page_source, 'html.parser')

    time_element = soup.select_one(settings.TIME_SELECTOR)
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
  # [수정] Docker 환경에서 헤드리스 브라우저의 안정적인 실행을 위한 표준 옵션들을 추가합니다.
  # 이것이 현재 멈춤 현상을 해결하는 핵심적인 수정 사항입니다.
  options.add_argument("--disable-extensions")
  options.add_argument("--disable-setuid-sandbox")
  options.add_argument("--remote-debugging-port=9222")

  options.binary_location = "/usr/bin/chromium"

  service = Service(executable_path="/usr/bin/chromedriver")

  print("[DEBUG] Selenium WebDriver를 생성합니다...")
  driver = webdriver.Chrome(service=service, options=options)
  print("[DEBUG] WebDriver 생성 완료.")

  final_results = []
  try:
    driver.set_page_load_timeout(30)
    for gallery in settings.GALLERIES_TO_SCRAPE:
      gallery_id, gallery_name = gallery["id"], gallery["name"]
      list_url = f"{settings.BASE_URL}/board/lists/?id={gallery_id}&exception_mode=recommend"
      print(f"--- [ {gallery_name} ] 확인 중 ---")

      response = requests.get(list_url, headers={'User-Agent': 'Mozilla/5.0'})
      soup = BeautifulSoup(response.text, 'html.parser')
      post_links = [settings.BASE_URL + tag['href'] for row in
                    soup.select(settings.POST_ROW_SELECTOR) if
                    (tag := row.select_one(settings.POST_LINK_SELECTOR))]

      for link in post_links:
        try:
          driver.get(link)
          page_source = driver.page_source
        except TimeoutException:
          print(f"  [경고] 페이지 로딩 시간 초과: {link}")
          continue
        except Exception as e:
          print(f"  [경고] 페이지 로딩 중 알 수 없는 오류: {link}, 에러: {e}")
          continue

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
