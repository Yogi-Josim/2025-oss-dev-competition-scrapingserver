import asyncio
from datetime import datetime
from app.utils.gpt_analyzer import extract_location_data_with_gpt

async def process_and_analyze_posts(candidate_posts: list) -> list:
    """
    수집된 후보 게시물 목록을 받아 정렬, GPT 분석, 최종 데이터 조합을 수행하는 공통 함수.
    """
    if not candidate_posts:
        print("[DEBUG] 분석할 게시물이 없어 종료합니다.")
        return []

    # 1단계: 수집된 모든 후보 게시물을 최신순으로 정렬
    print(f"[DEBUG] 총 {len(candidate_posts)}개의 후보 게시물 수집 완료. 시간순으로 정렬합니다...")
    candidate_posts.sort(key=lambda x: x.get('post_time', datetime.min), reverse=True)

    # 2단계: 수집된 모든 게시물을 동시에 분석 요청 (최대 효율)
    print(f"[DEBUG] GPT 동시 분석을 시작합니다...")
    tasks = [extract_location_data_with_gpt(post["raw_content"]) for post in candidate_posts]
    location_results = await asyncio.gather(*tasks)

    # 3단계: 분석 결과를 원본 데이터와 합쳐 최종 결과 리스트 생성
    final_results = []
    for i, post in enumerate(candidate_posts):
        location_info = location_results[i]
        post.update(location_info)
        post.pop('post_time', None)
        post["crawled_at"] = datetime.now().isoformat()
        final_results.append(post)

    print(f"[DEBUG] GPT 분석 및 최종 데이터 병합 완료. 총 {len(final_results)}개의 게시물 반환.")
    return final_results
