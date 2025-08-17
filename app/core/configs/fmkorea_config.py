from pydantic import BaseModel
from typing import List, Dict

class FmkoreaSettings(BaseModel):
  BASE_URL: str = "https://www.fmkorea.com"

  BOARDS_TO_SCRAPE: List[Dict[str, str]] = [
    {
      "id": "humor",
      "category": "1899663",
      "order_type": "desc",
      "listStyle": "webzine",
      "name": "유머/이슈 게시판",
    },
  ]

  POST_ROW_SELECTOR: str = "ul.bd_lst li.li"
  POST_LINK_SELECTOR: str = "a.hx"
  TITLE_SELECTOR: str = "h1.np_18px"
  CONTENT_SELECTOR: str = "article > div.xe_content"
  TIME_SELECTOR: str = "span.time"
  AUTHOR_SELECTOR: str = "span.by"
  COMMENT_SELECTOR: str = "span.comment"


fmkorea_settings = FmkoreaSettings()
