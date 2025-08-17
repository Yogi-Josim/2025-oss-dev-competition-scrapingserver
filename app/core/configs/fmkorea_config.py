# app/core/configs/fmkorea_config.py

from pydantic import BaseModel
from typing import List, Dict

class FmkoreaSettings(BaseModel):
    BASE_URL: str = "https://www.fmkorea.com"

    BOARDS_TO_SCRAPE: List[Dict[str, str]] = [
        # [수정] 'category' 키를 추가하여 스크래핑할 게시판을 더 구체적으로 지정합니다.
        {"id": "humor", "category": "1899663", "name": "유머/이슈 게시판"},
    ]

    # CSS 선택자
    POST_ROW_SELECTOR: str = "tbody tr:not(.notice)"
    POST_LINK_SELECTOR: str = "td.title > a:first-of-type"
    TITLE_SELECTOR: str = "h1.np_18px"
    CONTENT_SELECTOR: str = "article > div.xe_content"
    TIME_SELECTOR: str = "div.top_area > span.date"

# 설정 객체 생성
fmkorea_settings = FmkoreaSettings()
