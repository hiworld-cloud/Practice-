"""DB 테이블 정의.

여러 언어로 된 값(이름, 주소, 소개 등)은 {"ko": ..., "en": ..., "ja": ..., "zh": ...}
형태의 JSON 그대로 저장합니다.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column, UniqueConstraint
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


class Review(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    clinic_id: str = Field(foreign_key="clinic.id", index=True)
    rating: int
    nick: str
    # 사용자가 쓴 후기는 문자열, 샘플 후기는 언어별 dict
    text: Any = Field(default="", sa_column=Column(JSON, nullable=False))
    guest_id: Optional[str] = Field(default=None, index=True)
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
