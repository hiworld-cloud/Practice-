"""데이터베이스 연결.

DATABASE_URL 환경변수가 없으면 backend/beautybook.db (SQLite 파일)를 씁니다.
배포할 때는 Render의 환경변수에 Supabase(PostgreSQL) 주소를 넣으면 됩니다.
  예) DATABASE_URL=postgresql://postgres.abcd:비밀번호@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres
Supabase가 주는 주소(postgresql:// 또는 postgres://)를 그대로 붙여 넣어도 되도록
아래 normalize_url()이 psycopg 드라이버용 주소(postgresql+psycopg://)로 바꿔 줍니다.
"""
import os
from pathlib import Path

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

DEFAULT_DB = Path(__file__).resolve().parent.parent / "beautybook.db"


def normalize_url(url: str) -> str:
    url = url.strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = normalize_url(os.getenv("DATABASE_URL") or f"sqlite:///{DEFAULT_DB}")
IS_SQLITE = DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # pool_pre_ping: 오래 쉬다가 끊긴 연결을 쓰기 전에 확인해서 다시 연결해요 (무료 서버가 잠들었다 깰 때 필요).
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=3, max_overflow=2)


def create_tables(bind=None) -> None:
    from . import models  # noqa: F401  (테이블 정의를 등록하기 위해 import)

    bind = bind or engine
    SQLModel.metadata.create_all(bind)
    add_missing_columns(bind)


# create_all()은 "없는 테이블"만 만들고, 이미 있는 테이블에 새 칸(컬럼)을 추가하지는 않아요.
# 그래서 Supabase에 이미 있는 테이블에 새로 생긴 칸을 여기서 직접 추가해요. (아주 간단한 마이그레이션)
NEW_COLUMNS = [
    ("review", "user_id", "INTEGER"),  # 4단계: 카카오 로그인 회원 번호
]


def add_missing_columns(bind) -> None:
    insp = inspect(bind)
    with bind.begin() as conn:
        for table, column, sql_type in NEW_COLUMNS:
            if column not in {c["name"] for c in insp.get_columns(table)}:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_{column} ON {table} ({column})"))


def get_session():
    with Session(engine) as session:
        yield session
