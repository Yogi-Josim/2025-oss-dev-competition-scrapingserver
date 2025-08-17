from fastapi import APIRouter
from app.services.dcinside_scraping import run_dcinside_scraper

router = APIRouter()

@router.get("/dcinside")
async def scrape_dcinside_endpoint(hours: int = 0, minutes: int = 0):
    print(f"'/scrape/dcinside' 요청 수신. {hours}시간 {minutes}분 내의 글을 스크래핑합니다.")
    results = await run_dcinside_scraper(crawl_hours=hours, crawl_minutes=minutes)
    print(f"스크래핑 완료. 총 {len(results)}개의 게시물 반환.")
    return {"status": "success", "count": len(results), "data": results}
