import asyncio
from datetime import datetime
from sqlalchemy.orm import Session

from app.utils.gpt_analyzer import extract_location_data_with_gpt
from app.db import save_crawled_data, CrawledDataCreate


async def process_and_analyze_posts(candidate_posts: list, db: Session) -> list:
  if not candidate_posts:
    print("[DEBUG] 분석할 게시물이 없어 종료합니다.")
    return []

  print(f"[DEBUG] 총 {len(candidate_posts)}개의 후보 게시물 수집 완료. 시간순으로 정렬합니다...")
  candidate_posts.sort(key=lambda x: x.get('post_time', datetime.min),
                       reverse=True)

  print(f"[DEBUG] GPT 동시 분석을 시작합니다...")
  tasks = [extract_location_data_with_gpt(post["raw_content"]) for post in
           candidate_posts]
  location_results = await asyncio.gather(*tasks)

  final_data_to_save = []
  for i, post in enumerate(candidate_posts):
    location_info = location_results[i]
    gpt_comment = f"\n\n--- GPT Analysis ---\nRegion: {location_info.get('region')}\nPlace: {location_info.get('place_name')}\nLat: {location_info.get('latitude')}\nLon: {location_info.get('longitude')}"
    data_for_db = {
      "source_community": post["source_community"],
      "source_url": post["source_url"],
      "raw_content": post["raw_content"] + gpt_comment,
      "created_at": datetime.now()  # crawled_at을 created_at으로 변경
    }

    validated_data = CrawledDataCreate(**data_for_db)
    final_data_to_save.append(validated_data)

  save_crawled_data(db, final_data_to_save)

  return final_data_to_save
