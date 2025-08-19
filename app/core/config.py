# app/core/config.py
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Dict

load_dotenv()

# --- Scraper Specific Settings ---
class DcinsideSettings(BaseModel):
    BASE_URL: str = "https://gall.dcinside.com"
    GALLERIES_TO_SCRAPE: List[Dict[str, str]] = [
        {"id": "neostock", "name": "주식 갤러리"},
        {"id": "suneung", "name": "수능 갤러리"},
    ]
    POST_ROW_SELECTOR: str = "tr.us-post"
    POST_LINK_SELECTOR: str = "td.gall_tit a:not(.reply_numbox)"
    TITLE_SELECTOR: str = "span.title_subject"
    CONTENT_SELECTOR: str = "div.writing_view_box"
    TIME_SELECTOR: str = "span.gall_date"

class FmkoreaSettings(BaseModel):
    BASE_URL: str = "https://www.fmkorea.com"
    BOARDS_TO_SCRAPE: List[Dict[str, str]] = [
        {"id": "humor", "category": "1899663", "order_type": "desc", "name": "유머/이슈 게시판"},
    ]
    POST_ROW_SELECTOR: str = "tbody tr:not(.notice)"
    POST_LINK_SELECTOR: str = "td.title > a:first-of-type"
    TITLE_SELECTOR: str = "h1.np_18px"
    CONTENT_SELECTOR: str = "article > div.xe_content"
    TIME_SELECTOR: str = "div.top_area > span.date"

# --- Main Settings ---
class Settings(BaseModel):
    # API Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")

    # Database connection
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_USER: str = os.getenv("DB_USER", "user")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "password")
    DB_NAME: str = os.getenv("DB_NAME", "scraper_db")
    DB_PORT: int = int(os.getenv("DB_PORT", 3306))
    DATABASE_URL: str = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    # Scraper configs
    dcinside: DcinsideSettings = DcinsideSettings()
    fmkorea: FmkoreaSettings = FmkoreaSettings()

settings = Settings()
