# scraper-api-repo/app/api/endpoints/dcinside.py

from fastapi import APIRouter
from app.services.scraping import run_dcinside_scraper

router = APIRouter()

@router.get("/dcinside")
def scrape_dcinside_endpoint(hours: int = 24):
    """
    DCinside 갤러리들을 스크래핑하여 결과를 JSON으로 반환합니다.
    - hours: 현재로부터 몇 시간 전의 글까지 스크래핑할지 결정 (기본값: 24)
    """
    print(f"'/scrape/dcinside' 요청 수신. {hours}시간 내의 글을 스크래핑합니다.")
    results = run_dcinside_scraper(crawl_hours=hours)
    print(f"스크래핑 완료. 총 {len(results)}개의 게시물 반환.")
    return {"status": "success", "count": len(results), "data": results}