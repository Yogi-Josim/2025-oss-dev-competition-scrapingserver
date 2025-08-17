# app/services/fmkorea_scraping.py

import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, TimeoutException
# [추가] 똑똑하게 기다리는 기능을 위해 Selenium의 WebDriverWait를 임포트합니다.
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from app.core.configs.fmkorea_config import fmkorea_settings
from app.services.scraping_processor import process_and_analyze_posts


def _create_driver():
  """Docker 환경에서 실행 가능한 Selenium WebDriver 객체를 생성합니다."""
  chrome_options = Options()
  chrome_options.add_argument("--headless")
  chrome_options.add_argument("--no-sandbox")
  chrome_options.add_argument("--disable-dev-shm-usage")
  chrome_options.add_argument("--disable-gpu")
  chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")

  try:
    service = Service(executable_path='/usr/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver
  except WebDriverException as e:
    print(f"  [오류] Selenium WebDriver 생성 실패: {e}")
    return None


def _parse_fmkorea_time(time_str: str) -> datetime:
  """
  [핵심 수정] 상세 페이지의 절대적인 시간 형식만 처리하도록 함수를 간소화합니다.
  """
  time_str = time_str.strip()

  # Case 1: "YYYY.MM.DD HH:MM" (가장 흔한 형식)
  try:
    return datetime.strptime(time_str, '%Y.%m.%d %H:%M')
  except ValueError:
    pass

  # Case 2: "HH:MM" (오늘 날짜로 처리)
  try:
    now = datetime.now()
    parsed_time = datetime.strptime(time_str, '%H:%M')
    return now.replace(hour=parsed_time.hour, minute=parsed_time.minute,
                       second=0, microsecond=0)
  except ValueError:
    pass

  # Case 3: "YYYY.MM.DD"
  try:
    return datetime.strptime(time_str, '%Y.%m.%d')
  except ValueError:
    pass

  # 모든 형식에 맞지 않으면 실패로 처리
  return datetime.min


def _scrape_fmkorea_details(page_source: str, time_cutoff: datetime,
    source_community: str, current_url: str):
  try:
    soup = BeautifulSoup(page_source, 'html.parser')
    time_element = soup.select_one(fmkorea_settings.TIME_SELECTOR)

    if not time_element:
      print(f"  [정보] 시간 태그를 찾을 수 없어 건너뜁니다: {current_url}")
      return None

    post_time_str = time_element.text.strip()
    post_time = _parse_fmkorea_time(post_time_str)

    if post_time == datetime.min:
      print(f"  [정보] 시간 형식('{post_time_str}')을 파악할 수 없어 건너뜁니다: {current_url}")
      return None

    if post_time < time_cutoff:
      return "STOP"

    title = soup.select_one(fmkorea_settings.TITLE_SELECTOR).text.strip()
    content = soup.select_one(fmkorea_settings.CONTENT_SELECTOR).text.strip()

    return {"source_community": source_community, "source_url": current_url,
            "raw_content": f"{title}\n\n{content}", "post_time": post_time}
  except Exception as e:
    print(f"  [오류] Fmkorea 파싱 중 오류: {e}")
    return None


def run_fmkorea_scraper(crawl_hours: int):
  time_cutoff = datetime.now() - timedelta(hours=crawl_hours)
  candidate_posts = []
  driver = _create_driver()

  if not driver:
    return []

  try:
    for board in fmkorea_settings.BOARDS_TO_SCRAPE:
      board_id, board_name, category_id, order_type = board["id"], board[
        "name"], board.get("category"), board.get("order_type")
      list_url = f"{fmkorea_settings.BASE_URL}/index.php?mid={board_id}"
      if category_id: list_url += f"&category={category_id}"
      if order_type: list_url += f"&order_type={order_type}"

      print(f"--- [ 에펨코리아 - {board_name} ] 게시물 수집 중 (URL: {list_url}) ---")
      driver.get(list_url)

      # [핵심 수정] 게시물 목록(tr)이 나타날 때까지 최대 10초간 기다립니다.
      try:
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, fmkorea_settings.POST_ROW_SELECTOR)))
      except TimeoutException:
        print(f"  [오류] {board_name} 목록을 불러오는 데 시간이 너무 오래 걸립니다.")
        continue  # 다음 게시판으로 넘어감

      soup = BeautifulSoup(driver.page_source, 'html.parser')
      post_links = [fmkorea_settings.BASE_URL + tag['href'] for tag in
                    soup.select(fmkorea_settings.POST_LINK_SELECTOR)]

      for link in post_links:
        try:
          driver.get(link)
          result_data = _scrape_fmkorea_details(driver.page_source, time_cutoff,
                                                f"fmkorea_{board_id}", link)

          if result_data is None: continue
          if result_data == "STOP":
            print(f"  [정보] 시간 범위를 벗어난 게시물에 도달하여 {board_name} 수집을 중단합니다.")
            break
          candidate_posts.append(result_data)
        except Exception as e:
          print(f"  [경고] '{link}' 게시물 수집 중 오류: {e}")
  finally:
    if driver:
      driver.quit()

  import asyncio
  return asyncio.run(process_and_analyze_posts(candidate_posts))
