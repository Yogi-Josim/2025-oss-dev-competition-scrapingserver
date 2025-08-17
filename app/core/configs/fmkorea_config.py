from pydantic import BaseModel
from typing import List, Dict

class FmkoreaSettings(BaseModel):
    BASE_URL: str = "https://www.fmkorea.com"

    BOARDS_TO_SCRAPE: List[Dict[str, str]] = [
        {"id": "humor", "category": "1899663", "order_type": "desc", "name": "유머/이슈 게시판"},
    ]

    # CSS 선택자
    POST_ROW_SELECTOR: str = "tbody tr:not(.notice)"
    POST_LINK_SELECTOR: str = "td.title > a:first-of-type"
    TITLE_SELECTOR: str = "h1.np_18px"
    CONTENT_SELECTOR: str = "article > div.xe_content"
    TIME_SELECTOR: str = "div.top_area > span.date"

# 설정 객체 생성
fmkorea_settings = FmkoreaSettings()
