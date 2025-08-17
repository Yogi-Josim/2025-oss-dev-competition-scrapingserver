import asyncio
from datetime import datetime, timedelta

import httpx
from bs4 import BeautifulSoup

# [변경] fmkorea용 설정 파일을 임포트합니다.
from app.core.configs.fmkorea_config import fmkorea_settings
from app.utils.gpt_analyzer import extract_location_data_with_gpt


def _parse_fmkorea_time(time_str: str) -> datetime:
  """
  에펨코리아의 시간 형식('YYYY.MM.DD HH:MM' 또는 'HH:MM')을 datetime으로 변환합니다.
  """
  try:
    # 'HH:MM' 형식은 오늘 날짜로 처리
    if ":" in time_str and "." not in time_str:
      today_str = datetime.now().strftime("%Y.%m.%d")
      return datetime.strptime(f"{today_str} {time_str}", "%Y.%m.%d %H:%M")
    # 'YYYY.MM.DD' 형식 처리
    elif "." in time_str and ":" not in time_str:
      return datetime.strptime(time_str, "%Y.%m.%d")
    # 'YYYY.MM.DD HH:MM' 형식 처리
    else:
      return datetime.strptime(time_str, "%Y.%m.%d %H:%M")
  except ValueError:
    return datetime.min


def _scrape_fmkorea_details(page_source: str, time_cutoff: datetime,
    source_community: str, current_url: str):
  """
  에펨코리아 게시물 세부 정보를 파싱합니다.
  """
  try:
    soup = BeautifulSoup(page_source, 'html.parser')

    time_element = soup.select_one(fmkorea_settings.TIME_SELECTOR)
    post_time_str = time_element.text.strip() if time_element else ''
    post_time = _parse_fmkorea_time(post_time_str)

    if post_time == datetime.min:
      return None
    if post_time < time_cutoff:
      return "STOP"

    title_element = soup.select_one(fmkorea_settings.TITLE_SELECTOR)
    title = title_element.text.strip() if title_element else "제목 없음"

    content_element = soup.select_one(fmkorea_settings.CONTENT_SELECTOR)
    content = content_element.text.strip() if content_element else ""

    raw_content = f"{title}\n\n{content}"

    return {
      "source_community": source_community,
      "source_url": current_url,
      "raw_content": raw_content,
      "post_time": post_time
    }
  except Exception as e:
    print(f"  [오류] BeautifulSoup 파싱 중 오류: {e}")
    return None


async def run_fmkorea_scraper(crawl_hours: int):
  """
  에펨코리아를 스크래핑하고, 수집된 모든 게시물을 GPT로 분석합니다.
  (run_dcinside_scraper와 로직은 동일하고, 사용하는 설정과 함수만 다릅니다.)
  """
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

            result_data = _scrape_fmkorea_details(
                post_response.text,
                time_cutoff,
                f"fmkorea_{board_id}",
                link
            )

            if result_data is None:
              continue
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

  print(f"[DEBUG] 총 {len(candidate_posts)}개의 후보 게시물 수집 완료. 시간순으로 정렬합니다...")
  candidate_posts.sort(key=lambda x: x.get('post_time', datetime.min),
                       reverse=True)

  if not candidate_posts:
    print("[DEBUG] 분석할 게시물이 없어 종료합니다.")
    return []

  print(
    f"[DEBUG] 분석할 최신 게시물 {len(candidate_posts)}개를 선택했습니다. GPT 동시 분석을 시작합니다...")
  tasks = [extract_location_data_with_gpt(post["raw_content"]) for post in
           candidate_posts]
  location_results = await asyncio.gather(*tasks)

  final_results = []
  for i, post in enumerate(candidate_posts):
    location_info = location_results[i]
    post.update(location_info)
    post.pop('post_time', None)
    post["crawled_at"] = datetime.now().isoformat()
    final_results.append(post)

  print(f"[DEBUG] GPT 분석 및 최종 데이터 병합 완료. 총 {len(final_results)}개의 게시물 반환.")
  return final_results
