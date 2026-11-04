"""데이터베이스 연결.

DATABASE_URL 환경변수가 없으면 backend/beautybook.db (SQLite 파일)를 씁니다.
나중에 Supabase/Neon 같은 PostgreSQL로 옮길 때는 환경변수만 바꾸면 됩니다.
  예) DATABASE_URL=postgresql+psycopg://user:pass@host:5432/beautybook
"""
import os
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

DEFAULT_DB = Path(__file__).resolve().parent.parent / "beautybook.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB}")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)


def create_tables(bind=None) -> None:
    from . import models  # noqa: F401  (테이블 정의를 등록하기 위해 import)

    SQLModel.metadata.create_all(bind or engine)


def get_session():
    with Session(engine) as session:
        yield session
