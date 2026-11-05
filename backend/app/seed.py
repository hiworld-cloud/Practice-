"""샘플 병원과 샘플 리뷰를 DB에 넣습니다. 이미 있는 병원은 건너뜁니다.

실행: (backend 폴더에서) python -m app.seed
나중에 공공데이터 API로 진짜 병원을 가져오면 이 파일을 그 스크립트로 바꾸면 됩니다.
"""
import json
from pathlib import Path

from sqlmodel import Session, select

from .db import create_tables, engine
from .models import Clinic, Review

SEED_FILE = Path(__file__).resolve().parent / "seed_data.json"


def load_seed() -> dict:
    return json.loads(SEED_FILE.read_text(encoding="utf-8"))


def seed(session: Session) -> int:
    # 이미 병원이 하나라도 있으면(공공데이터를 넣었거나 샘플을 지운 경우) 다시 넣지 않습니다.
    if session.exec(select(Clinic.id).limit(1)).first():
        return 0
    data = load_seed()
    added = 0
    for c in data["clinics"]:
        if session.get(Clinic, c["id"]):
            continue
        session.add(
            Clinic(
                id=c["id"],
                name=c["name"],
                area=c["area"],
                address=c["address"],
                phone=c["phone"],
                specialties=c["specialties"],
                about=c["about"],
                doctors=c["doctors"],
                procedures=c["procedures"],
                hours_open=c["hours"]["open"],
                hours_close=c["hours"]["close"],
                closed_days=c["closedDays"],
                hue=c.get("hue", 0),
            )
        )
        for r in c.get("reviews", []):
            session.add(Review(clinic_id=c["id"], rating=r["rating"], nick=r["nick"], text=r["text"]))
        added += 1
    session.commit()
    return added


if __name__ == "__main__":
    create_tables()
    with Session(engine) as s:
        print(f"added {seed(s)} clinics")
