import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, \
  StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
# [추가] WebDriverWait와 Expected Conditions를 임포트합니다.
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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
    # [수정] 각 요소가 화면에 나타날 때까지 최대 10초간 기다립니다.
    # 이 방법이 Stale Element Reference 에러를 해결하는 가장 표준적인 방법입니다.
    wait = WebDriverWait(driver, 10)

    time_element = wait.until(
      EC.presence_of_element_located((By.CSS_SELECTOR, settings.TIME_SELECTOR)))
    post_time_str = time_element.get_attribute('title')
    post_time = _parse_time(post_time_str)

    if not post_time or post_time < time_cutoff:
      return "STOP"

    title = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, settings.TITLE_SELECTOR))).text
    content = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, settings.CONTENT_SELECTOR))).text
    raw_content = f"{title}\n\n{content}"

    # 댓글은 동적으로 로딩될 수 있으므로, 잠시 기다린 후 수집합니다.
    # presence_of_all_elements_located를 사용해 모든 댓글 요소를 기다립니다.
    comment_elements = wait.until(EC.presence_of_all_elements_located(
        (By.CSS_SELECTOR, settings.COMMENT_LIST_SELECTOR)))
    comments = [el.text for el in comment_elements if el.text]

    return {
      "source_community": source_community, "source_url": driver.current_url,
      "raw_content": raw_content, "crawled_at": datetime.now().isoformat(),
      "comments": comments
    }
  # [수정] StaleElementReferenceException을 명시적으로 처리하여 안정성을 높입니다.
  except StaleElementReferenceException:
    print("  [경고] Stale Element 에러 발생. 다음 게시물로 넘어갑니다.")
    return None
  except Exception as e:
    print(f"  [오류] 상세 정보 스크래핑 중 오류: {e}")
    return None


def run_dcinside_scraper(crawl_hours: int):
  time_cutoff = datetime.now() - timedelta(hours=crawl_hours)

  options = webdriver.ChromeOptions()
  options.add_argument('--headless=new')
  options.add_argument('--no-sandbox')
  options.add_argument('--disable-dev-shm-usage')
  options.add_argument('--disable-gpu')
  options.add_argument("--window-size=1920,1080")

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
    driver.quit()

  return final_results
