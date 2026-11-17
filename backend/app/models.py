"""DB 테이블 정의.

여러 언어로 된 값(이름, 주소, 소개 등)은 {"ko": ..., "en": ..., "ja": ..., "zh": ...}
형태의 JSON 그대로 저장합니다.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, BigInteger, Boolean, Column, String, UniqueConstraint, false
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Clinic(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: dict = Field(sa_column=Column(JSON, nullable=False))
    area: dict = Field(sa_column=Column(JSON, nullable=False))
    address: dict = Field(sa_column=Column(JSON, nullable=False))
    phone: str
    specialties: list = Field(sa_column=Column(JSON, nullable=False))
    about: dict = Field(sa_column=Column(JSON, nullable=False))
    doctors: list = Field(sa_column=Column(JSON, nullable=False))
    procedures: list = Field(sa_column=Column(JSON, nullable=False))
    hours_open: str  # "10:00"
    hours_close: str  # "19:00"
    closed_days: list = Field(sa_column=Column(JSON, nullable=False))  # 0=일요일 ... 6=토요일
    hue: int = 0  # 카드 색상


class User(SQLModel, table=True):
    """회원. 카카오로 가입했거나 이메일로 가입했어요.
    ("user"는 PostgreSQL 예약어라서 테이블 이름을 app_user로 해요.)"""
    __tablename__ = "app_user"

    id: Optional[int] = Field(default=None, primary_key=True)
    # 카카오로 가입한 사람만 있어요. 회원번호는 숫자가 커서(10자리 이상) BigInteger로 저장해요.
    kakao_id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, unique=True, nullable=True, index=True))
    # 이메일로 가입한 사람만 있어요. 항상 소문자로 저장해요.
    email: Optional[str] = Field(default=None, sa_column=Column(String(254), unique=True, nullable=True, index=True))
    # 비밀번호 원문이 아니라 "알아볼 수 없게 바꾼 값"(해시)만 저장해요. email_login.py 참고
    password_hash: Optional[str] = None
    # 메일로 보낸 링크를 눌러서 "진짜 내 이메일"임을 확인했는지. 확인 전에는 이메일 로그인이 안 돼요.
    email_verified: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default=false()))
    nickname: str = ""
    created_at: datetime = Field(default_factory=_now)
    last_login_at: datetime = Field(default_factory=_now)


class Review(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    clinic_id: str = Field(foreign_key="clinic.id", index=True)
    rating: int
    nick: str
    # 사용자가 쓴 후기는 문자열, 샘플 후기는 언어별 dict
    text: Any = Field(default="", sa_column=Column(JSON, nullable=False))
    guest_id: Optional[str] = Field(default=None, index=True)  # 로그인 기능 전에 쓴 리뷰
    user_id: Optional[int] = Field(default=None, index=True)  # 쓴 회원 (app_user.id)
    created_at: datetime = Field(default_factory=_now)


class Reservation(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("clinic_id", "date", "time", name="uq_reservation_slot"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    clinic_id: str = Field(foreign_key="clinic.id", index=True)
    guest_id: str = Field(index=True)
    name: str
    phone: str
    procedure: str
    date: str  # "2026-11-05"
    time: str  # "10:30"
    memo: str = ""
    status: str = "requested"
    created_at: datetime = Field(default_factory=_now)
