# app/services/scraping.py

import asyncio
from datetime import datetime, timedelta

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.utils.gpt_analyzer import extract_location_data_with_gpt


def _scrape_post_details(page_source: str, time_cutoff: datetime,
    source_community: str, current_url: str):
  """
  BeautifulSoup를 사용하여 게시물 세부 정보를 파싱합니다.
  - 파싱 실패 시: None 반환
  - 시간 초과 시: "STOP" 반환
  - 성공 시: 데이터 딕셔너리 반환
  """
  try:
    soup = BeautifulSoup(page_source, 'html.parser')

    time_element = soup.select_one(settings.TIME_SELECTOR)
    post_time_str = time_element.get('title') if time_element else ''
    post_time = _parse_time(post_time_str)

    # [수정] 1. 시간 파싱 실패를 먼저 처리합니다.
    # 공지, 광고 등 시간이 없는 글은 건너뛰기 위해 None을 반환합니다.
    if post_time == datetime.min:
      print(f"  [정보] '{current_url}' 게시물의 시간을 파싱할 수 없어 건너뜁니다.")
      return None

    # [수정] 2. 파싱이 성공한 경우에만 시간 범위를 확인합니다.
    if post_time < time_cutoff:
      return "STOP"

    title_element = soup.select_one(settings.TITLE_SELECTOR)
    title = title_element.text.strip() if title_element else "제목 없음"

    content_element = soup.select_one(settings.CONTENT_SELECTOR)
    content = content_element.text.strip() if content_element else ""

    raw_content = f"{title}\n\n{content}"

    return {
      "source_community": source_community,
      "source_url": current_url,
      "raw_content": raw_content,
      "crawled_at": "",
      "region": "",
      "place_name": "",
      "latitude": None,
      "longitude": None,
      "post_time": post_time
    }
  except Exception as e:
    print(f"  [오류] BeautifulSoup 파싱 중 오류: {e}")
    return None


def _parse_time(time_str: str) -> datetime:
  """시간 문자열을 datetime 객체로 변환합니다."""
  try:
    return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
  except ValueError:
    return datetime.min


async def run_dcinside_scraper(crawl_hours: int):
  """DCinside 갤러리를 비동기적으로 스크래핑하고 GPT로 지역 정보를 분석합니다."""
  time_cutoff = datetime.now() - timedelta(hours=crawl_hours)
  final_results = []

  headers = {'User-Agent': 'Mozilla/5.0'}

  async with httpx.AsyncClient(headers=headers, timeout=30.0) as aclient:
    for gallery in settings.GALLERIES_TO_SCRAPE:
      gallery_id, gallery_name = gallery["id"], gallery["name"]
      list_url = f"{settings.BASE_URL}/board/lists/?id={gallery_id}&exception_mode=recommend"
      print(f"--- [ {gallery_name} ] 목록 확인 중 ---")
      stop_gallery_scraping = False  # [수정] 갤러리 스크래핑 중단을 위한 플래그

      try:
        list_response = await aclient.get(list_url)
        list_response.raise_for_status()
        soup = BeautifulSoup(list_response.text, 'html.parser')
        post_links = [settings.BASE_URL + tag['href'] for row in
                      soup.select(settings.POST_ROW_SELECTOR) if
                      (tag := row.select_one(settings.POST_LINK_SELECTOR))]

        MAX_RETRIES = 3
        RETRY_DELAY = 2  # 초

        for link in post_links:
          for attempt in range(MAX_RETRIES):
            try:
              post_response = await aclient.get(link)
              post_response.raise_for_status()

              result_data = _scrape_post_details(
                  post_response.text,
                  time_cutoff,
                  f"dcinside_{gallery_id}",
                  link
              )

              # [수정] 반환값에 따른 분기 처리 로직 개선
              if result_data is None:  # Case 1: 파싱 실패 -> 이 게시물만 건너뜀
                break  # 재시도 루프 탈출 후 다음 link로 이동

              if result_data == "STOP":  # Case 2: 시간 초과 -> 이 갤러리 스크래핑 중단
                stop_gallery_scraping = True
                break

              # Case 3: 성공
              location_info = await extract_location_data_with_gpt(
                  result_data["raw_content"])
              result_data.update(location_info)
              result_data["crawled_at"] = datetime.now().isoformat()
              final_results.append(result_data)
              break

            except httpx.RequestError as e:
              if attempt < MAX_RETRIES - 1:
                print(
                  f"  [경고] '{link}' 요청 실패 ({repr(e)}). {RETRY_DELAY}초 후 재시도합니다... ({attempt + 1}/{MAX_RETRIES})")
                await asyncio.sleep(RETRY_DELAY)
              else:
                print(f"  [오류] '{link}' 게시물을 가져오는 데 최종 실패했습니다: {repr(e)}")

          if stop_gallery_scraping:
            print(
              f"  [정보] 시간 범위({crawl_hours}시간)를 벗어난 게시물에 도달하여 {gallery_name} 스크래핑을 중단합니다.")
            break

      except httpx.RequestError as e:
        print(f"  [오류] {gallery_name} 목록을 가져오는 중 오류 발생: {repr(e)}")

  print(f"[DEBUG] 스크래핑 완료. 결과를 시간순으로 정렬합니다...")
  final_results.sort(key=lambda x: x.get('post_time', datetime.min),
                     reverse=True)

  for result in final_results:
    result.pop('post_time', None)

  print(f"[DEBUG] 정렬 완료. 총 {len(final_results)}개의 유효한 게시물 발견.")
  return final_results
