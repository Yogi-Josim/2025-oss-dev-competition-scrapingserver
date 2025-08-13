import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
import requests
from bs4 import BeautifulSoup
from app.core.config import settings


def _parse_time(time_str: str) -> datetime:
  try:
    return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
  except ValueError:
    return None


def _scrape_details(driver: webdriver.Chrome, time_cutoff: datetime,
    source_community: str):
  try:
    time_element = driver.find_element(By.CSS_SELECTOR, settings.TIME_SELECTOR)
    post_time_str = time_element.get_attribute('title')
    post_time = _parse_time(post_time_str)

    if not post_time or post_time < time_cutoff:
      return "STOP"

    print(f"    [성공] 시간 내 게시물 ({post_time.strftime('%Y-%m-%d %H:%M')})...")
    title = driver.find_element(By.CSS_SELECTOR, settings.TITLE_SELECTOR).text
    content = driver.find_element(By.CSS_SELECTOR,
                                  settings.CONTENT_SELECTOR).text
    raw_content = f"{title}\n\n{content}"
    comments = [el.text for el in driver.find_elements(By.CSS_SELECTOR,
                                                       settings.COMMENT_LIST_SELECTOR)
                if el.text]

    return {
      "source_community": source_community,
      "source_url": driver.current_url,
      "raw_content": raw_content,
      "crawled_at": datetime.now().isoformat(),
      "comments": comments
    }
  except Exception:
    return None


def run_dcinside_scraper(crawl_hours: int):
  time_cutoff = datetime.now() - timedelta(hours=crawl_hours)

  options = webdriver.ChromeOptions()
  options.add_argument('--headless=new')
  options.add_argument('--no-sandbox')
  options.add_argument('--disable-dev-shm-usage')
  options.add_argument('--disable-gpu')

  SELENIUM_GRID_URL = "http://localhost:4444/wd/hub"

  print("Selenium Grid에 연결을 시도합니다...")
  driver = webdriver.Remote(
      command_executor=SELENIUM_GRID_URL,
      options=options
  )
  print("WebDriver 생성 완료.")

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
          print(f"[DEBUG] 게시물 접속 시도 (최대 30초): {link}")
          driver.get(link)
          print(f"[DEBUG] 페이지 로딩 완료: {link}")
        except TimeoutException:
          print(f"  [경고] 페이지 로딩 시간 초과: {link}")
          continue
        except Exception as e:
          print(f"  [경고] 페이지 로딩 중 알 수 없는 오류: {link}, 에러: {e}")
          continue

        result = _scrape_details(driver, time_cutoff, f"dcinside_{gallery_id}")
        if result == "STOP":
          break
        elif result:
          final_results.append(result)

  finally:
    print("[DEBUG] 스크래핑 루프 종료. WebDriver를 닫습니다.")
    if driver:
      driver.quit()

  return final_results