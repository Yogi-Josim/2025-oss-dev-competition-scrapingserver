import time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, \
  TimeoutError as PlaywrightTimeoutError
import requests
from bs4 import BeautifulSoup
from app.core.config import settings


# [수정] 병렬 처리에 사용되던 Queue와 Thread를 제거합니다.


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

    # 댓글 수집 로직을 완전히 제거합니다.
    return {
      "source_community": source_community, "source_url": current_url,
      "raw_content": raw_content, "crawled_at": datetime.now().isoformat(),
      "comments": [],  # 항상 빈 리스트를 반환합니다.
      "post_time": post_time
    }
  except Exception as e:
    print(f"  [오류] BeautifulSoup 파싱 중 오류: {e}")
    return None


# [수정] 메인 스크래핑 함수를 단일 스레드로 간단하게 작동하도록 재설계합니다.
def run_dcinside_scraper(crawl_hours: int):
  time_cutoff = datetime.now() - timedelta(hours=crawl_hours)
  final_results = []

  # 1. 모든 갤러리에서 스크래핑할 링크 목록을 먼저 수집합니다.
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
        all_links_to_scrape.append((link, gallery_id))
    except Exception as e:
      print(f"  [오류] {gallery_name} 목록을 가져오는 중 오류 발생: {e}")

  # 2. Playwright를 사용하여 수집된 링크들을 순서대로 처리합니다.
  print(f"총 {len(all_links_to_scrape)}개의 게시물을 순차적으로 스크래핑합니다...")
  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    for link, gallery_id in all_links_to_scrape:
      try:
        # 'domcontentloaded'는 HTML 구조가 완성되는 시점을 의미하여 매우 빠릅니다.
        page.goto(link, timeout=20000, wait_until='domcontentloaded')
        page_source = page.content()

        result = _scrape_details_with_bs(
            page_source,
            time_cutoff,
            f"dcinside_{gallery_id}",
            page.url
        )
        if result == "STOP":
          # 한 갤러리에서 시간 범위를 벗어난 게시물이 나오면,
          # 그 갤러리의 나머지 게시물은 건너뛰는 것이 효율적일 수 있습니다.
          # 여기서는 간단하게 모든 링크를 확인합니다.
          pass
        elif result:
          final_results.append(result)
      except Exception as e:
        print(f"  [오류] '{link}' 처리 중 오류 발생: {e}")

    browser.close()

  # 3. 모든 스크래핑이 끝난 후, 결과를 시간순으로 정렬합니다.
  print(f"[DEBUG] 스크래핑 완료. 결과를 시간순으로 정렬합니다...")
  final_results.sort(key=lambda x: x.get('post_time', datetime.min),
                     reverse=True)

  for result in final_results:
    result.pop('post_time', None)

  print(f"[DEBUG] 정렬 완료. 총 {len(final_results)}개의 유효한 게시물 발견.")
  return final_results
