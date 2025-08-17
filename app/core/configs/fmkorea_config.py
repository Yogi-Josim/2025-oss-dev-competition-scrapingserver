from pydantic import BaseModel
from typing import List, Dict

class FmkoreaSettings(BaseModel):
  BASE_URL: str = "https://www.fmkorea.com"

  BOARDS_TO_SCRAPE: List[Dict[str, str]] = [
    {
      "id": "humor",
      "category": "1899663",
      "order_type": "desc",
      "sort_index": "regdate",
      "listStyle": "webzine",
      "name": "유머/이슈 게시판",
    },
  ]

  POST_ROW_SELECTOR: str = "ul.fm_best_widget li.li"
  POST_LINK_SELECTOR: str = "h3.title > a"
  TITLE_SELECTOR: str = "h3.title > a"
  CONTENT_SELECTOR: str = "div.se_component_wrap, div.xe_content"
  TIME_SELECTOR: str = "span.regdate"
  AUTHOR_SELECTOR: str = "span.author"
  COMMENT_SELECTOR: str = "span.comment_count"


fmkorea_settings = FmkoreaSettings()
