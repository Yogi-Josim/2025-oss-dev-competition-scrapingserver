# app/utils/gpt_analyzer.py

import os
import json
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
    GPT를 사용하여 텍스트에서 지역 정보, 장소 이름, GPS 좌표를 JSON 형식으로 추출합니다.
    이 함수는 다른 서비스에서 공용으로 사용할 수 있습니다.

    Args:
        content: 분석할 원본 텍스트 (게시물 본문, 뉴스 기사 등).

    Returns:
        추출된 위치 정보가 담긴 딕셔너리.
    """
    if not client:
        print("OpenAI client is not available. Returning UNKNOWN.")
        return {"region": "UNKNOWN", "place_name": "UNKNOWN", "latitude": None, "longitude": None}

    system_prompt = """
    You are a highly intelligent assistant specializing in extracting specific location information from Korean text.
    Your task is to identify locations and return the data ONLY in a valid JSON format.
    The JSON object must contain these four keys: "region", "place_name", "latitude", "longitude".
    """
    user_prompt = f"""
    Analyze the following text and extract location information based on these rules:

    1.  **Prioritize Specificity**: Identify the MOST specific and contextually important location mentioned. A specific station name (e.g., '오산역') is more important than a general city name (e.g., '서울').

    2.  **Find Landmarks**: Look for specific landmarks, institutions, stations, or company names (e.g., '서울대병원', '오산역환승센터', '경복궁').
        - If found, identify its precise location.
        - Set 'place_name' to the identified name (e.g., "오산역").
        - Set 'region' to its correct '시/도 시/군/구' address (e.g., "경기도 오산시"). **Crucially, do NOT incorrectly combine different administrative districts.** For example, Osan is in Gyeonggi-do, not Seoul.
        - Provide its precise latitude and longitude.

    3.  **Find Explicit Addresses**: If no specific landmark is found, look for an explicit address like '서울시 강남구' or '부산 해운대구'.
        - If found, set 'region' to that value and 'place_name' to 'UNKNOWN'.
        - Use a representative GPS coordinate for that region.

    4.  **Default to UNKNOWN**: If no reliable location information is found, all values in the JSON must be "UNKNOWN", with latitude and longitude set to null.

    5.  **JSON Only**: Your response MUST be ONLY the JSON object, with no additional text or explanations.

    --- EXAMPLES ---

    Example 1 (Specific Station):
    Text: "서울(오산) -> 부산 평일 시내버스 여행... 7번 버스 막차를 타고 오산역으로 갔음."
    Response:
    {{
      "region": "경기도 오산시",
      "place_name": "오산역",
      "latitude": 37.1483,
      "longitude": 127.0716
    }}

    Example 2 (Landmark):
    Text: "3년 전 환자 성폭력한 산과 전공의 징계 안 한 서울대병원"
    Response:
    {{
      "region": "서울시 종로구",
      "place_name": "서울대학교병원",
      "latitude": 37.5795,
      "longitude": 126.9996
    }}

    Example 3 (No Location):
    Text: "오늘 날씨가 정말 좋네요."
    Response:
    {{
      "region": "UNKNOWN",
      "place_name": "UNKNOWN",
      "latitude": null,
      "longitude": null
    }}

    --- Text to Analyze ---
    {content}
    """
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        response_content = response.choices[0].message.content
        location_data = json.loads(response_content)
        return location_data

    except Exception as e:
        print(f"An error occurred while calling OpenAI API or parsing JSON: {e}")
        return {"region": "UNKNOWN", "place_name": "UNKNOWN", "latitude": None, "longitude": None}
