from datetime import datetime, timedelta
import httpx
from bs4 import BeautifulSoup

from app.core.configs.fmkorea_config import fmkorea_settings
from app.services.scraping_processor import process_and_analyze_posts


def _parse_fmkorea_time(time_str: str) -> datetime:
  try:
    if ":" in time_str and "." not in time_str:
      today_str = datetime.now().strftime("%Y.%m.%d")
      return datetime.strptime(f"{today_str} {time_str}", "%Y.%m.%d %H:%M")
    elif "." in time_str and ":" not in time_str:
      return datetime.strptime(time_str, "%Y.%m.%d")
    else:
      return datetime.strptime(time_str, "%Y.%m.%d %H:%M")
  except ValueError:
    return datetime.min


def _scrape_fmkorea_details(page_source: str, time_cutoff: datetime,
    source_community: str, current_url: str):
  try:
    soup = BeautifulSoup(page_source, 'html.parser')
    time_element = soup.select_one(fmkorea_settings.TIME_SELECTOR)
    post_time_str = time_element.text.strip() if time_element else ''
    post_time = _parse_fmkorea_time(post_time_str)

    if post_time == datetime.min: return None
    if post_time < time_cutoff: return "STOP"

    title = soup.select_one(fmkorea_settings.TITLE_SELECTOR).text.strip()
    content = soup.select_one(fmkorea_settings.CONTENT_SELECTOR).text.strip()

    return {
      "source_community": source_community,
      "source_url": current_url,
      "raw_content": f"{title}\n\n{content}",
      "post_time": post_time
    }
  except Exception as e:
    print(f"  [오류] Fmkorea 파싱 중 오류: {e}")
    return None


async def run_fmkorea_scraper(crawl_hours: int):
  time_cutoff = datetime.now() - timedelta(hours=crawl_hours)
  candidate_posts = []
  headers = {'User-Agent': 'Mozilla/5.0'}

  async with httpx.AsyncClient(headers=headers, timeout=30.0) as aclient:
    for board in fmkorea_settings.BOARDS_TO_SCRAPE:
      board_id, board_name = board["id"], board["name"]
      list_url = f"{fmkorea_settings.BASE_URL}/index.php?mid={board_id}"
      print(f"--- [ 에펨코리아 - {board_name} ] 게시물 수집 중 ---")
      stop_board_scraping = False

      try:
        list_response = await aclient.get(list_url)
        list_response.raise_for_status()
        soup = BeautifulSoup(list_response.text, 'html.parser')
        post_links = [fmkorea_settings.BASE_URL + tag['href'] for tag in
                      soup.select(fmkorea_settings.POST_LINK_SELECTOR)]

        for link in post_links:
          try:
            post_response = await aclient.get(link)
            post_response.raise_for_status()
            result_data = _scrape_fmkorea_details(post_response.text,
                                                  time_cutoff,
                                                  f"fmkorea_{board_id}", link)

            if result_data is None: continue
            if result_data == "STOP":
              stop_board_scraping = True
              break
            candidate_posts.append(result_data)
          except httpx.RequestError as e:
            print(f"  [경고] '{link}' 게시물 수집 중 오류: {repr(e)}")

        if stop_board_scraping:
          print(f"  [정보] 시간 범위를 벗어난 게시물에 도달하여 {board_name} 수집을 중단합니다.")
      except httpx.RequestError as e:
        print(f"  [오류] {board_name} 목록을 가져오는 중 오류 발생: {repr(e)}")

  # [변경] 수집된 데이터를 공용 처리 모듈로 넘겨 결과를 반환합니다.
  return await process_and_analyze_posts(candidate_posts)
