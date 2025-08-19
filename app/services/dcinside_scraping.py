import asyncio
from datetime import datetime, timedelta
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.scraping_processor import process_and_analyze_posts


def _parse_dcinside_time(time_str: str) -> datetime:
  try:
    return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
  except ValueError:
    return datetime.min


def _scrape_dcinside_details(
    page_source: str,
    time_cutoff: datetime,
    source_community: str,
    current_url: str
):
  try:
    soup = BeautifulSoup(page_source, 'html.parser')
    time_element = soup.select_one(settings.dcinside.TIME_SELECTOR)
    post_time_str = time_element.get('title') if time_element else ''
    post_time = _parse_dcinside_time(post_time_str)

    if post_time == datetime.min or post_time < time_cutoff:
      return None

    title = soup.select_one(settings.dcinside.TITLE_SELECTOR).text.strip()
    content = soup.select_one(settings.dcinside.CONTENT_SELECTOR).text.strip()

    return {"source_community": source_community, "source_url": current_url,
            "raw_content": f"{title}\n\n{content}", "post_time": post_time}
  except Exception as e:
    print(f"  [오류] DCinside 파싱 중 오류: {e}")
    return None


async def run_dcinside_scraper(crawl_hours: int, crawl_minutes: int,
    db: Session):
  if crawl_hours == 0 and crawl_minutes == 0:
    crawl_hours = 24
  time_cutoff = datetime.now() - timedelta(hours=crawl_hours,
                                           minutes=crawl_minutes)

  candidate_posts = []
  headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'}

  async with httpx.AsyncClient(headers=headers, timeout=30.0,
                               follow_redirects=True) as aclient:
    for gallery in settings.dcinside.GALLERIES_TO_SCRAPE:
      gallery_id, gallery_name = gallery["id"], gallery["name"]
      list_url = f"{settings.dcinside.BASE_URL}/board/lists/?id={gallery_id}&exception_mode=recommend"
      print(f"--- [ DCinside - {gallery_name} ] 게시물 수집 중 ---")

      try:
        list_response = await aclient.get(list_url)
        list_response.raise_for_status()
        soup = BeautifulSoup(list_response.text, 'html.parser')
        post_links = [settings.dcinside.BASE_URL + tag['href'] for row in
                      soup.select(settings.dcinside.POST_ROW_SELECTOR) if (
                        tag := row.select_one(
                          settings.dcinside.POST_LINK_SELECTOR))]

        tasks = [fetch_and_parse_post(aclient, link, time_cutoff,
                                      f"dcinside_{gallery_id}") for link in
                 post_links]
        results = await asyncio.gather(*tasks)

        for result in results:
          if result: candidate_posts.append(result)

      except httpx.RequestError as e:
        print(f"  [오류] {gallery_name} 목록을 가져오는 중 오류 발생: {repr(e)}")

  return await process_and_analyze_posts(candidate_posts, db)


async def fetch_and_parse_post(aclient: httpx.AsyncClient, link: str,
    time_cutoff: datetime, source_community: str):
  try:
    response = await aclient.get(link)
    response.raise_for_status()
    return _scrape_dcinside_details(response.text, time_cutoff,
                                    source_community, link)
  except httpx.RequestError as e:
    print(f"  [경고] '{link}' 게시물 수집 중 오류: {repr(e)}")
    return None
