# scraper-api-repo/app/core/config.py

from pydantic import BaseModel
from typing import List, Dict


class Settings(BaseModel):
  BASE_URL: str = "https://gall.dcinside.com"

  GALLERIES_TO_SCRAPE: List[Dict[str, str]] = [
    {"id": "neostock", "name": "주식 갤러리"},
    {"id": "suneung", "name": "수능 갤러리"},
    {"id": "baseball_new11", "name": "국내야구 갤러리"},
    {"id": "w_entertainer", "name": "여자 연예인 갤러리"},
    {"id": "dcbest", "name": "실시간 베스트"},
  ]

  # CSS 선택자
  POST_ROW_SELECTOR: str = "tr.us-post"
  POST_LINK_SELECTOR: str = "td.gall_tit a:not(.reply_numbox)"
  TITLE_SELECTOR: str = "span.title_subject"
  CONTENT_SELECTOR: str = "div.writing_view_box"
  TIME_SELECTOR: str = "span.gall_date"
  COMMENT_LIST_SELECTOR: str = ".cmt_list li"
  COMMENT_USER_TEXT_SELECTOR: str = ".usertxt"
  COMMENT_DCCON_SELECTOR: str = ".written_dccon"
  COMMENT_AD_SELECTOR: str = ".dori-box"


# 설정 객체 생성
settings = Settings()