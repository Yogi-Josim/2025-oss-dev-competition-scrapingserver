from fastapi import APIRouter
from app.services.fmkorea_scraping import run_fmkorea_scraper

router = APIRouter()

@router.get("/fmkorea")
async def scrape_fmkorea_endpoint(hours: int = 24):
    """
    에펨코리아 게시판을 스크래핑하여 결과를 JSON으로 반환합니다.
    - hours: 현재로부터 몇 시간 전의 글까지 스크래핑할지 결정 (기본값: 24)
    """
    print(f"'/scrape/fmkorea' 요청 수신. {hours}시간 내의 글을 스크래핑합니다.")
    results = await run_fmkorea_scraper(crawl_hours=hours)
    print(f"스크래핑 완료. 총 {len(results)}개의 게시물 반환.")
    return {"status": "success", "count": len(results), "data": results}
