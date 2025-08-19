# app/db.py
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, \
  BigInteger, Boolean
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

from app.core.config import settings

# 1. DB 연결 설정
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# 2. [핵심 수정] 테이블 구조를 'crawled_data'에 완벽하게 일치시킵니다.
class CrawledData(Base):
  __tablename__ = "crawled_data"
  id = Column(BigInteger, primary_key=True, index=True)
  source_community = Column(String(255), nullable=False)
  source_url = Column(String(255), unique=True, nullable=False)
  raw_content = Column(Text, nullable=False)
  created_at = Column(DateTime(6))
  processed = Column(Boolean, default=False)
  region_id = Column(BigInteger, nullable=True)


# 3. [핵심 수정] DB에 저장될 데이터의 유효성 검사 규칙을 테이블에 맞게 변경합니다.
class CrawledDataCreate(BaseModel):
  source_community: str
  source_url: str
  raw_content: str
  created_at: datetime
  # region, place_name 등 테이블에 없는 필드는 제거합니다.


# 4. 실제 데이터 저장 함수
def save_crawled_data(db: Session, data_to_save: List[CrawledDataCreate]):
  if not data_to_save:
    return

  existing_urls = {
    item[0] for item in db.query(CrawledData.source_url)
    .filter(CrawledData.source_url.in_([p.source_url for p in data_to_save]))
    .all()
  }

  new_data = [
    # [핵심 수정] processed와 region_id의 기본값을 설정합니다.
    CrawledData(
        **p.dict(),
        processed=False,
        region_id=None
    ) for p in data_to_save if p.source_url not in existing_urls
  ]

  if not new_data:
    print("[DEBUG] 저장할 새로운 게시물이 없습니다 (모두 중복).")
    return

  try:
    db.bulk_save_objects(new_data)
    db.commit()
    print(f"[DEBUG] {len(new_data)}개의 새로운 게시물을 성공적으로 저장했습니다.")
  except Exception as e:
    db.rollback()
    print(f"[오류] 데이터베이스 저장 중 오류 발생: {e}")


# 5. API에서 사용할 DB 세션 제공 함수
def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()
