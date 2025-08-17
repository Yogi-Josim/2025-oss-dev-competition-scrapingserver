from fastapi import FastAPI
# [수정] dcinside와 fmkorea 라우터를 각각 임포트합니다.
from app.api.endpoints import dcinside, fmkorea

app = FastAPI(
    title="Community Scraper API",
    description="다양한 커뮤니티의 게시물을 스크래핑하는 API입니다.",
    version="0.1.0"
)

# '/scrape' 경로 하위에 각 커뮤니티의 엔드포인트들을 포함시킵니다.
app.include_router(dcinside.router, prefix="/scrape", tags=["Scraping"])
app.include_router(fmkorea.router, prefix="/scrape", tags=["Scraping"]) # [추가]

@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Scraper API is running"}
