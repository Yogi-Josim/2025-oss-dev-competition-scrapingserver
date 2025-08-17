import asyncio
from datetime import datetime, timedelta

import httpx
from bs4 import BeautifulSoup

from app.core.configs.dcinside_config import settings
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

    if post_time == datetime.min:
      return None

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
  """
  DCinside 갤러리를 스크래핑하고, 수집된 모든 게시물을 GPT로 분석합니다.
  """
  time_cutoff = datetime.now() - timedelta(hours=crawl_hours)
  candidate_posts = []

  headers = {'User-Agent': 'Mozilla/_5.0'}

  async with httpx.AsyncClient(headers=headers, timeout=30.0) as aclient:
    # 1단계: 모든 갤러리를 순회하며 시간 범위 내의 게시물 후보들을 수집
    for gallery in settings.GALLERIES_TO_SCRAPE:
      gallery_id, gallery_name = gallery["id"], gallery["name"]
      list_url = f"{settings.BASE_URL}/board/lists/?id={gallery_id}&exception_mode=recommend"
      print(f"--- [ {gallery_name} ] 게시물 수집 중 ---")
      stop_gallery_scraping = False

      try:
        list_response = await aclient.get(list_url)
        list_response.raise_for_status()
        soup = BeautifulSoup(list_response.text, 'html.parser')
        post_links = [settings.BASE_URL + tag['href'] for row in
                      soup.select(settings.POST_ROW_SELECTOR) if
                      (tag := row.select_one(settings.POST_LINK_SELECTOR))]

        for link in post_links:
          try:
            post_response = await aclient.get(link)
            post_response.raise_for_status()

            result_data = _scrape_post_details(
                post_response.text,
                time_cutoff,
                f"dcinside_{gallery_id}",
                link
            )

            if result_data is None:
              continue
            if result_data == "STOP":
              stop_gallery_scraping = True
              break

            candidate_posts.append(result_data)

          except httpx.RequestError as e:
            print(f"  [경고] '{link}' 게시물 수집 중 오류: {repr(e)}")

        if stop_gallery_scraping:
          print(f"  [정보] 시간 범위를 벗어난 게시물에 도달하여 {gallery_name} 수집을 중단합니다.")

      except httpx.RequestError as e:
        print(f"  [오류] {gallery_name} 목록을 가져오는 중 오류 발생: {repr(e)}")

  # 2단계: 수집된 모든 후보 게시물을 최신순으로 정렬
  print(f"[DEBUG] 총 {len(candidate_posts)}개의 후보 게시물 수집 완료. 시간순으로 정렬합니다...")
  candidate_posts.sort(key=lambda x: x.get('post_time', datetime.min),
                       reverse=True)

  # 3단계: 수집된 모든 게시물을 동시에 분석 요청 (최대 효율)
  print(
    f"[DEBUG] 분석할 최신 게시물 {len(candidate_posts)}개를 선택했습니다. GPT 동시 분석을 시작합니다...")
  if not candidate_posts:
    print("[DEBUG] 분석할 게시물이 없어 종료합니다.")
    return []

  tasks = [extract_location_data_with_gpt(post["raw_content"]) for post in
           candidate_posts]
  location_results = await asyncio.gather(*tasks)

  # 4단계: 분석 결과를 원본 데이터와 합쳐 최종 결과 리스트 생성
  final_results = []
  for i, post in enumerate(candidate_posts):
    location_info = location_results[i]
    post.update(location_info)
    post.pop('post_time', None)
    post["crawled_at"] = datetime.now().isoformat()
    final_results.append(post)

  print(f"[DEBUG] GPT 분석 및 최종 데이터 병합 완료. 총 {len(final_results)}개의 게시물 반환.")
  return final_results
