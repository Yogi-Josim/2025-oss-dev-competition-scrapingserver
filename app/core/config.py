# app/core/config.py
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from app.core.configs.dcinside_config import DcinsideSettings, dcinside_settings
from app.core.configs.fmkorea_config import FmkoreaSettings, fmkorea_settings

load_dotenv()

class Settings(BaseModel):
  # API Keys
  OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")

  # [수정] Database connection
  DB_HOST: str = os.getenv("DB_HOST", "host.docker.internal")
  DB_USER: str = os.getenv("DB_USER", "admin")
  DB_PASSWORD: str = os.getenv("DB_PASSWORD", "00000000")
  DB_NAME: str = os.getenv("DB_NAME", "yogi-josim")
  DB_PORT: int = int(os.getenv("DB_PORT", 3306))
  DATABASE_URL: str = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

  # Scraper configs
  dcinside: DcinsideSettings = dcinside_settings
  fmkorea: FmkoreaSettings = fmkorea_settings


settings = Settings()
