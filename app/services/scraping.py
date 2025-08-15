import time
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from app.core.config import settings


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

    return {
      "source_community": source_community, "source_url": current_url,
      "raw_content": raw_content, "crawled_at": datetime.now().isoformat(),
      "post_time": post_time
    }
  except Exception as e:
    print(f"  [오류] BeautifulSoup 파싱 중 오류: {e}")
    return None


def run_dcinside_scraper(crawl_hours: int):
  time_cutoff = datetime.now() - timedelta(hours=crawl_hours)
  final_results = []

  # 세션을 사용하여 TCP 연결을 재사용하므로 성능이 향상됩니다.
  session = requests.Session()
  session.headers.update({'User-Agent': 'Mozilla/5.0'})

  for gallery in settings.GALLERIES_TO_SCRAPE:
    gallery_id, gallery_name = gallery["id"], gallery["name"]
    list_url = f"{settings.BASE_URL}/board/lists/?id={gallery_id}&exception_mode=recommend"
    print(f"--- [ {gallery_name} ] 목록 확인 중 ---")

    try:
      # 1. 게시물 목록 페이지를 가져옵니다.
      response = session.get(list_url)
      response.raise_for_status()
      soup = BeautifulSoup(response.text, 'html.parser')
      post_links = [settings.BASE_URL + tag['href'] for row in
                    soup.select(settings.POST_ROW_SELECTOR) if
                    (tag := row.select_one(settings.POST_LINK_SELECTOR))]

      # 2. 각 게시물 링크를 순회하며 내용을 가져옵니다.
      for link in post_links:
        try:
          post_response = session.get(link, timeout=10)
          post_response.raise_for_status()

          result = _scrape_details_with_bs(
              post_response.text,
              time_cutoff,
              f"dcinside_{gallery_id}",
              link
          )

          if result == "STOP":
            # 시간 범위를 벗어난 게시물이 나오면 해당 갤러리의 나머지 스크래핑을 중단합니다.
            print(
              f"  [정보] 시간 범위({crawl_hours}시간)를 벗어난 게시물에 도달하여 {gallery_name} 스크래핑을 중단합니다.")
            break
          elif result:
            final_results.append(result)

        except requests.RequestException as e:
          print(f"  [경고] '{link}' 게시물을 가져오는 중 오류 발생: {e}")

    except requests.RequestException as e:
      print(f"  [오류] {gallery_name} 목록을 가져오는 중 오류 발생: {e}")

  # 모든 스크래핑이 끝난 후, 결과를 시간순으로 정렬합니다.
  print(f"[DEBUG] 스크래핑 완료. 결과를 시간순으로 정렬합니다...")
  final_results.sort(key=lambda x: x.get('post_time', datetime.min),
                     reverse=True)

  for result in final_results:
    result.pop('post_time', None)

  print(f"[DEBUG] 정렬 완료. 총 {len(final_results)}개의 유효한 게시물 발견.")
  return final_results
