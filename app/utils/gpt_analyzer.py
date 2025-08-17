# app/utils/gpt_analyzer.py

import os
import json
import asyncio
import openai  # openai.RateLimitError를 잡기 위해 임포트
from openai import AsyncOpenAI
from dotenv import load_dotenv

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


async def extract_location_data_with_gpt(content: str) -> dict:
  """
  GPT를 사용하여 텍스트에서 지역 정보를 추출합니다.
  Rate Limit 오류 발생 시 지수 백오프(exponential backoff) 재시도 로직을 포함합니다.
  """
  if not client:
    print("OpenAI client is not available. Returning UNKNOWN.")
    return {"region": "UNKNOWN", "place_name": "UNKNOWN", "latitude": None,
            "longitude": None}

  system_prompt = """
You are an AI that extracts location data from Korean text. Respond ONLY with a valid JSON object: {"region": "...", "place_name": "...", "latitude": ..., "longitude": ...}.

Rules:
1.  **Prioritize specific landmarks** (e.g., '오산역') over general areas.
2.  `place_name` is the landmark's name; `region` is its correct '시/도 시/군/구' address.
3.  If no landmark, find an address (e.g., '서울시 강남구') for `region` and set `place_name` to "UNKNOWN".
4.  If no location, use "UNKNOWN" or null for all values.
5.  **Do not merge unrelated districts** (e.g., Osan is in Gyeonggi-do, not Seoul).

Example 1:
Text: "서울(오산) -> 부산... 오산역으로 갔음."
JSON: {"region": "경기도 오산시", "place_name": "오산역", "latitude": 37.1483, "longitude": 127.0716}

Example 2:
Text: "징계 안 한 서울대병원"
JSON: {"region": "서울시 종로구", "place_name": "서울대학교병원", "latitude": 37.5795, "longitude": 126.9996}
"""

  max_retries = 3
  delay = 2  # 초

  for attempt in range(max_retries):
    try:
      response = await client.chat.completions.create(
          model="gpt-5-mini",
          messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
          ],
          # [수정] gpt-5-mini 모델에서 지원하지 않는 temperature 파라미터를 제거합니다.
          response_format={"type": "json_object"}
      )
      response_content = response.choices[0].message.content
      location_data = json.loads(response_content)
      return location_data

    except openai.RateLimitError as e:
      if attempt < max_retries - 1:
        content_snippet = content.replace('\n', ' ').strip()[:40]
        print(
          f"  [경고] OpenAI Rate Limit. '{content_snippet}...' 내용 재시도 ({attempt + 1}/{max_retries}). {delay}초 후 다시 시도합니다.")
        await asyncio.sleep(delay)
        delay *= 2  # 대기 시간 2배 증가
      else:
        print(f"  [오류] OpenAI API Rate Limit 재시도 모두 실패: {e}")
        return {"region": "UNKNOWN", "place_name": "UNKNOWN", "latitude": None,
                "longitude": None}

    except Exception as e:
      print(f"  [오류] OpenAI API 호출 또는 JSON 파싱 중 오류 발생: {e}")
      return {"region": "UNKNOWN", "place_name": "UNKNOWN", "latitude": None,
              "longitude": None}

  return {"region": "UNKNOWN", "place_name": "UNKNOWN", "latitude": None,
          "longitude": None}
