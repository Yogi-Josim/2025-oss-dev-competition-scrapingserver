# app/services/scraping.py

import os
import asyncio
from datetime import datetime, timedelta

import httpx
from bs4 import BeautifulSoup
from openai import AsyncOpenAI
from dotenv import load_dotenv

from app.core.config import settings

# .env 파일에서 환경 변수를 로드합니다.
load_dotenv()

# OpenAI 클라이언트 초기화 (비동기)
try:
  client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
  if not client.api_key:
    raise ValueError("OPENAI_API_KEY environment variable not found.")
except Exception as e:
  print(f"Error initializing OpenAI client: {e}")
  client = None


async def extract_region_with_gpt(content: str) -> str:
  """
  GPT를 사용하여 텍스트에서 지역 정보를 비동기적으로 추출합니다.

  Args:
      content: 분석할 원본 텍스트 (게시물 본문).

  Returns:
      추출된 지역 정보 ('OO시 OO구' 형식) 또는 'UNKNOWN'.
  """
  if not client:
    print("OpenAI client is not available. Returning 'UNKNOWN'.")
    return "UNKNOWN"

  # GPT에 전달할 프롬프트
  system_prompt = "You are a helpful assistant specialized in extracting location information from Korean text. Your task is to find a location and format it as '시/도 구/군'."
  user_prompt = f"""
    다음 텍스트에서 언급된 지역 정보를 'OO시 OO구' 또는 'OO도 OO군' 형식으로 정확하게 추출해 주세요.
    만약 텍스트에 명확한 지역 정보가 없다면, 다른 어떤 설명도 없이 오직 'UNKNOWN'이라고만 응답해 주세요.

    - 예시 1: "서울 강남역 근처 맛집 좀 알려주세요." -> "서울시 강남구"
    - 예시 2: "부산 해운대에서 모임 있습니다." -> "부산시 해운대구"
    - 예시 3: "오늘 날씨 정말 좋네요." -> "UNKNOWN"
    - 예시 4: "경기도 성남시 분당구" -> "경기도 성남시" (구 단위까지만 추출)

    --- 분석할 텍스트 ---
    {content}
    --------------------
    """
  try:
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
          {"role": "system", "content": system_prompt},
          {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        max_tokens=50,
    )
    region = response.choices[0].message.content.strip()

    # 만약 GPT가 추가적인 텍스트를 반환할 경우를 대비한 후처리
    return "UNKNOWN" if "UNKNOWN" in region else region
  except Exception as e:
    print(f"An error occurred while calling OpenAI API: {e}")
    return "UNKNOWN"


def _parse_time(time_str: str) -> datetime:
  """시간 문자열을 datetime 객체로 변환합니다."""
  try:
    return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
  except ValueError:
    return datetime.min


def _scrape_post_details(page_source: str, time_cutoff: datetime,
    source_community: str, current_url: str):
  """
  BeautifulSoup를 사용하여 게시물 세부 정보를 파싱합니다. (동기 함수)
  이 함수는 네트워크 I/O가 없으므로 동기로 유지합니다.
  """
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

    # GPT 분석 및 최종 데이터 조립을 위해 파싱된 데이터를 반환합니다.
    return {
      "source_community": source_community,
      "source_url": current_url,
      "raw_content": raw_content,
      "crawled_at": "",  # 임시값, 나중에 채워짐
      "region": "",  # 임시값, GPT가 채울 예정
      "post_time": post_time
    }
  except Exception as e:
    print(f"  [오류] BeautifulSoup 파싱 중 오류: {e}")
    return None


async def run_dcinside_scraper(crawl_hours: int):
  """DCinside 갤러리를 비동기적으로 스크래핑하고 GPT로 지역 정보를 분석합니다."""
  time_cutoff = datetime.now() - timedelta(hours=crawl_hours)
  final_results = []

  headers = {'User-Agent': 'Mozilla/5.0'}

  async with httpx.AsyncClient(headers=headers, timeout=15) as aclient:
    for gallery in settings.GALLERIES_TO_SCRAPE:
      gallery_id, gallery_name = gallery["id"], gallery["name"]
      list_url = f"{settings.BASE_URL}/board/lists/?id={gallery_id}&exception_mode=recommend"
      print(f"--- [ {gallery_name} ] 목록 확인 중 ---")

      try:
        # 1. 게시물 목록 페이지를 비동기로 가져옵니다.
        list_response = await aclient.get(list_url)
        list_response.raise_for_status()
        soup = BeautifulSoup(list_response.text, 'html.parser')
        post_links = [settings.BASE_URL + tag['href'] for row in
                      soup.select(settings.POST_ROW_SELECTOR) if
                      (tag := row.select_one(settings.POST_LINK_SELECTOR))]

        # 2. 각 게시물 링크를 순회하며 내용을 비동기로 가져옵니다.
        for link in post_links:
          try:
            post_response = await aclient.get(link)
            post_response.raise_for_status()

            # 2a. 게시물 내용 파싱 (동기)
            result_data = _scrape_post_details(
                post_response.text,
                time_cutoff,
                f"dcinside_{gallery_id}",
                link
            )

            if result_data == "STOP":
              print(
                f"  [정보] 시간 범위({crawl_hours}시간)를 벗어난 게시물에 도달하여 {gallery_name} 스크래핑을 중단합니다.")
              break

            if result_data:
              # 2b. GPT로 지역 정보 추출 (비동기)
              region = await extract_region_with_gpt(result_data["raw_content"])

              # 2c. 최종 데이터 채우기
              result_data["region"] = region
              result_data["crawled_at"] = datetime.now().isoformat()
              final_results.append(result_data)

          except httpx.RequestError as e:
            print(f"  [경고] '{link}' 게시물을 가져오는 중 오류 발생: {e}")

      except httpx.RequestError as e:
        print(f"  [오류] {gallery_name} 목록을 가져오는 중 오류 발생: {e}")

  print(f"[DEBUG] 스크래핑 완료. 결과를 시간순으로 정렬합니다...")
  final_results.sort(key=lambda x: x.get('post_time', datetime.min),
                     reverse=True)

  # 정렬 후에는 더 이상 필요 없는 post_time 필드를 제거합니다.
  for result in final_results:
    result.pop('post_time', None)

  print(f"[DEBUG] 정렬 완료. 총 {len(final_results)}개의 유효한 게시물 발견.")
  return final_results
