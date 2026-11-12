"""BeautyBook API 서버 (FastAPI).

실행: (backend 폴더에서) uvicorn app.main:app --reload
  - http://localhost:8000          → 사이트 (서버 모드로 동작)
  - http://localhost:8000/docs     → API 문서 (직접 눌러 보며 테스트 가능)

리뷰 쓰기는 카카오로 로그인한 사람만 할 수 있어요 (auth.py 참고).
예약은 아직 브라우저마다 만든 임의의 ID(X-Guest-Id 헤더)로 "내 예약"을 구분합니다.
"""
import os
import re
from contextlib import asynccontextmanager
from datetime import date as Date
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Optional
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from . import auth, db
from .auth import OptionalUserDep, UserDep
from .models import Clinic, Reservation, Review, User
from .seed import load_seed, seed

KST = ZoneInfo("Asia/Seoul")
SITE_DIR = Path(__file__).resolve().parents[2]  # 저장소 루트 (index.html이 있는 곳)
SessionDep = Annotated[Session, Depends(db.get_session)]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.create_tables()
    with Session(db.engine) as s:
        # DB가 비어 있을 때만 가상 샘플 병원을 넣어요.
        # 공공데이터로 진짜 병원을 넣고 샘플을 지운 뒤에는 다시 생기지 않아요.
        if s.exec(select(Clinic).limit(1)).first() is None:
            seed(s)
    yield


app = FastAPI(title="BeautyBook API", version="0.1.0", lifespan=lifespan)

# 다른 주소(예: GitHub Pages)에서 이 API를 부를 수 있게 허용할 주소 목록. 쉼표로 구분.
_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Guest-Id", "Authorization"],
)
app.include_router(auth.router)


# ---------- 요청/응답 형태 ----------

class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    text: str = Field(default="", max_length=300)
    # 닉네임은 이제 카카오 닉네임을 써요. (예전 화면이 nick을 보내도 무시해요)


class ReservationIn(BaseModel):
    clinicId: str
    name: str = Field(min_length=1, max_length=50)
    phone: str = Field(min_length=4, max_length=30)
    procedure: str
    date: str
    time: str
    memo: str = Field(default="", max_length=500)


def guest_header(x_guest_id: Annotated[Optional[str], Header()] = None) -> str:
    if not x_guest_id or not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", x_guest_id):
        raise HTTPException(400, detail={"code": "guest_id_required"})
    return x_guest_id


GuestDep = Annotated[str, Depends(guest_header)]


def clinic_out(c: Clinic, rating: float, count: int) -> dict[str, Any]:
    return {
        "id": c.id, "name": c.name, "area": c.area, "address": c.address, "phone": c.phone,
        "specialties": c.specialties, "about": c.about, "doctors": c.doctors,
        "procedures": c.procedures, "hours": {"open": c.hours_open, "close": c.hours_close},
        "closedDays": c.closed_days, "hue": c.hue, "rating": rating, "count": count,
    }


def review_out(r: Review, user: Optional[User]) -> dict[str, Any]:
    return {
        "id": r.id, "rating": r.rating, "nick": r.nick, "text": r.text,
        "mine": bool(user and r.user_id == user.id),
        "createdAt": r.created_at.isoformat(),
    }


def reservation_out(r: Reservation) -> dict[str, Any]:
    return {
        "id": r.id, "clinicId": r.clinic_id, "name": r.name, "phone": r.phone,
        "procedure": r.procedure, "date": r.date, "time": r.time, "memo": r.memo,
        "status": r.status, "createdAt": r.created_at.isoformat(),
    }


def get_clinic_or_404(session: Session, clinic_id: str) -> Clinic:
    c = session.get(Clinic, clinic_id)
    if not c:
        raise HTTPException(404, detail={"code": "clinic_not_found"})
    return c


def time_slots(c: Clinic) -> list[str]:
    def to_min(s: str) -> int:
        h, m = s.split(":")
        return int(h) * 60 + int(m)

    out, m = [], to_min(c.hours_open)
    while m + 30 <= to_min(c.hours_close):
        out.append(f"{m // 60:02d}:{m % 60:02d}")
        m += 30
    return out


def parse_date(value: str) -> Date:
    try:
        return Date.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, detail={"code": "invalid_date"})


# ---------- API ----------

@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/meta")
def meta():
    data = load_seed()
    return {"specialties": data["specialties"], "procedures": data["procedures"]}


@app.get("/api/clinics")
def list_clinics(session: SessionDep):
    stats = dict(
        (cid, (avg, cnt))
        for cid, avg, cnt in session.exec(
            select(Review.clinic_id, func.avg(Review.rating), func.count(Review.id)).group_by(Review.clinic_id)
        )
    )
    clinics = session.exec(select(Clinic).order_by(Clinic.id)).all()
    return [clinic_out(c, float(stats.get(c.id, (0, 0))[0] or 0), int(stats.get(c.id, (0, 0))[1])) for c in clinics]


@app.get("/api/clinics/{clinic_id}")
def get_clinic(clinic_id: str, session: SessionDep):
    c = get_clinic_or_404(session, clinic_id)
    avg, cnt = session.exec(
        select(func.avg(Review.rating), func.count(Review.id)).where(Review.clinic_id == clinic_id)
    ).one()
    return clinic_out(c, float(avg or 0), int(cnt))


@app.get("/api/clinics/{clinic_id}/reviews")
def list_reviews(clinic_id: str, session: SessionDep, user: OptionalUserDep):
    get_clinic_or_404(session, clinic_id)
    rows = session.exec(
        select(Review).where(Review.clinic_id == clinic_id).order_by(Review.created_at.desc(), Review.id.desc())
    ).all()
    return [review_out(r, user) for r in rows]


@app.post("/api/clinics/{clinic_id}/reviews", status_code=201)
def add_review(clinic_id: str, body: ReviewIn, session: SessionDep, user: UserDep):
    """리뷰 쓰기: 카카오로 로그인한 사람만, 한 병원에 한 번만."""
    get_clinic_or_404(session, clinic_id)
    already = session.exec(
        select(Review.id).where(Review.clinic_id == clinic_id, Review.user_id == user.id)
    ).first()
    if already:
        raise HTTPException(409, detail={"code": "already_reviewed"})
    r = Review(clinic_id=clinic_id, rating=body.rating, nick=user.nickname or "카카오회원",
               text=body.text.strip(), user_id=user.id)
    session.add(r)
    session.commit()
    session.refresh(r)
    return review_out(r, user)


@app.get("/api/clinics/{clinic_id}/taken-slots")
def taken_slots(clinic_id: str, session: SessionDep, date: str = Query(...)):
    get_clinic_or_404(session, clinic_id)
    parse_date(date)
    return session.exec(
        select(Reservation.time).where(Reservation.clinic_id == clinic_id, Reservation.date == date)
    ).all()


@app.get("/api/reservations/me")
def my_reservations(session: SessionDep, guest_id: GuestDep):
    rows = session.exec(
        select(Reservation).where(Reservation.guest_id == guest_id).order_by(Reservation.date, Reservation.time)
    ).all()
    return [reservation_out(r) for r in rows]


@app.post("/api/reservations", status_code=201)
def create_reservation(body: ReservationIn, session: SessionDep, guest_id: GuestDep):
    c = get_clinic_or_404(session, body.clinicId)
    d = parse_date(body.date)
    today = datetime.now(KST).date()

    if body.procedure not in {p["key"] for p in c.procedures}:
        raise HTTPException(422, detail={"code": "invalid_procedure"})
    if body.time not in time_slots(c):
        raise HTTPException(422, detail={"code": "invalid_time"})
    if d < today or d > today + timedelta(days=60):
        raise HTTPException(422, detail={"code": "date_out_of_range"})
    if (d.isoweekday() % 7) in c.closed_days:  # isoweekday: 월=1..일=7 → 일=0
        raise HTTPException(422, detail={"code": "clinic_closed"})
    if d == today and body.time <= datetime.now(KST).strftime("%H:%M"):
        raise HTTPException(422, detail={"code": "time_passed"})

    r = Reservation(clinic_id=c.id, guest_id=guest_id, name=body.name.strip(), phone=body.phone.strip(),
                    procedure=body.procedure, date=body.date, time=body.time, memo=body.memo.strip())
    session.add(r)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, detail={"code": "slot_taken"})
    session.refresh(r)
    return reservation_out(r)


@app.delete("/api/reservations/{reservation_id}", status_code=204)
def cancel_reservation(reservation_id: int, session: SessionDep, guest_id: GuestDep):
    r = session.get(Reservation, reservation_id)
    if not r or r.guest_id != guest_id:
        raise HTTPException(404, detail={"code": "reservation_not_found"})
    session.delete(r)
    session.commit()
    return Response(status_code=204)


# ---------- 사이트 파일 제공 (서버 하나로 화면 + API를 같이 띄우기) ----------

@app.get("/js/config.js", include_in_schema=False)
def site_config():
    # 이 서버에서 사이트를 열면 API도 같은 주소를 쓰도록 알려 줍니다.
    return Response('window.BEAUTYBOOK_API_BASE = "";\n', media_type="application/javascript")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(SITE_DIR / "index.html")


app.mount("/css", StaticFiles(directory=SITE_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=SITE_DIR / "js"), name="js")
