from datetime import datetime, timedelta
import httpx
from bs4 import BeautifulSoup

from app.core.configs.fmkorea_config import fmkorea_settings
from app.services.scraping_processor import process_and_analyze_posts


def _parse_fmkorea_time(time_str: str) -> datetime:
  time_str = time_str.strip()
  try:
    return datetime.strptime(time_str, '%Y.%m.%d %H:%M')
  except ValueError:
    pass
  try:
    now = datetime.now()
    parsed_time = datetime.strptime(time_str, '%H:%M')
    return now.replace(hour=parsed_time.hour, minute=parsed_time.minute,
                       second=0, microsecond=0)
  except ValueError:
    pass
  try:
    return datetime.strptime(time_str, '%Y.%m.%d')
  except ValueError:
    return datetime.min


def _scrape_fmkorea_details(
    page_source: str,
    time_cutoff: datetime,
    source_community: str,
    current_url: str
):
  try:
    soup = BeautifulSoup(page_source, 'html.parser')
    time_element = soup.select_one(fmkorea_settings.TIME_SELECTOR)
    if not time_element: return None

    post_time_str = time_element.text.strip()
    post_time = _parse_fmkorea_time(post_time_str)

    if post_time == datetime.min: return None
    if post_time < time_cutoff: return "STOP"

    content_elem = soup.select_one(fmkorea_settings.CONTENT_SELECTOR)
    content = content_elem.get_text(" ", strip=True) if content_elem else None

    return {
      "source_community": source_community,
      "source_url": current_url,
      "raw_content": f"{title}\n\n{content}",
      "post_time": post_time
    }
  except Exception as e:
    print(f"  [오류] Fmkorea 파싱 중 오류: {e}")
    return None


async def run_fmkorea_scraper(crawl_hours: int, crawl_minutes: int):
  if crawl_hours == 0 and crawl_minutes == 0:
    crawl_hours = 1

  time_cutoff = datetime.now() - timedelta(hours=crawl_hours,
                                           minutes=crawl_minutes)
  candidate_posts = []
  headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': fmkorea_settings.BASE_URL
  }

  async with httpx.AsyncClient(
      headers=headers,
      timeout=30.0,
      follow_redirects=True
  ) as aclient:
    for board in fmkorea_settings.BOARDS_TO_SCRAPE:
      board_id = board["id"]
      board_name = board["name"]
      category_id = board.get("category")
      order_type = board.get("order_type")

      list_url = f"{fmkorea_settings.BASE_URL}/index.php?mid={board_id}"
      if category_id:
        list_url += f"&category={category_id}"
      if order_type:
        list_url += f"&order_type={order_type}"

      print(f"--- [ 에펨코리아 - {board_name} ] 게시물 수집 중 (URL: {list_url}) ---")
      stop_board_scraping = False

      try:
        list_response = await aclient.get(list_url)
        list_response.raise_for_status()
        soup = BeautifulSoup(list_response.text, 'html.parser')
        post_blocks = soup.select(fmkorea_settings.POST_ROW_SELECTOR)
        post_links = []
        for block in post_blocks:
          link_elem = block.select_one(fmkorea_settings.POST_LINK_SELECTOR)
          if link_elem and link_elem.has_attr("href"):
            post_links.append(fmkorea_settings.BASE_URL + link_elem["href"])

        for link in post_links:
          try:
            post_response = await aclient.get(link)
            post_response.raise_for_status()
            result_data = _scrape_fmkorea_details(
                post_response.text,
                time_cutoff,
                f"fmkorea_{board_id}",
                link
            )

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

  return await process_and_analyze_posts(candidate_posts)
