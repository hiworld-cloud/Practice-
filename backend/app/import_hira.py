"""공공데이터포털 '건강보험심사평가원_병원정보서비스'에서 성형외과 목록을 받아 DB에 넣습니다.

준비
  1. data.go.kr 에서 '건강보험심사평가원_병원정보서비스' 활용신청
  2. 마이페이지에 나오는 일반 인증키 중 **Decoding** 키를 환경변수로 설정
       export HIRA_SERVICE_KEY='발급받은_Decoding_키'
     (키는 코드나 git에 절대 넣지 마세요)

실행 (backend 폴더에서)
  python -m app.import_hira                       # 전국 성형외과 의원, 최대 100곳
  python -m app.import_hira --sido 110000         # 서울만
  python -m app.import_hira --limit 300           # 최대 300곳
  python -m app.import_hira --replace-samples     # 가상 샘플 병원 8곳은 지우고 진짜 병원만 남기기
  python -m app.import_hira --dry-run             # DB에 넣지 않고 받아온 목록만 출력

공공데이터에 없는 값
  - 진료 시간/휴진일: 기본값(10:00~19:00, 일요일 휴진)으로 넣고 hours_estimated=True 로 표시
  - 시술/가격: '일반 상담' 하나만 넣음 (가격 정보 없음)
  - 다국어 이름: 한국어 이름을 모든 언어에 그대로 사용
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Iterable, Optional

from sqlmodel import Session, select

from .db import create_tables, engine
from .models import Clinic, Reservation, Review

API_URL = "https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList"
PLASTIC_SURGERY = "08"  # 심평원 진료과목코드: 08 = 성형외과
CLINIC_LEVEL = "31"  # 심평원 종별코드: 31 = 의원 (큰 병원의 성형외과는 제외)
LANGS = ("ko", "en", "ja", "zh")

SIDO = {
    "110000": "서울", "210000": "부산", "220000": "인천", "230000": "대구", "240000": "광주",
    "250000": "대전", "260000": "울산", "410000": "경기", "420000": "강원", "430000": "충북",
    "440000": "충남", "450000": "전북", "460000": "전남", "470000": "경북", "480000": "경남",
    "490000": "제주", "290000": "세종",
}

Fetcher = Callable[[str], dict]


class HiraError(RuntimeError):
    pass


def http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            body = res.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as e:
        raise HiraError(f"공공데이터 서버에 연결하지 못했어요: {e}")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        # 키가 틀리면 JSON 대신 XML 오류(SERVICE_KEY_IS_NOT_REGISTERED_ERROR 등)가 오는 경우가 많습니다.
        raise HiraError(f"JSON이 아닌 응답을 받았어요. 인증키나 활용신청 상태를 확인해 주세요.\n{body[:300]}")


def build_url(service_key: str, page: int, rows: int, sido: Optional[str]) -> str:
    params = {
        "serviceKey": service_key,
        "pageNo": page,
        "numOfRows": rows,
        "dgsbjtCd": PLASTIC_SURGERY,
        "clCd": CLINIC_LEVEL,
        "_type": "json",
    }
    if sido:
        params["sidoCd"] = sido
    return API_URL + "?" + urllib.parse.urlencode(params)


def parse_page(data: dict) -> tuple[list[dict], int]:
    """응답에서 (병원 목록, 전체 개수)를 꺼냅니다."""
    resp = data.get("response", {})
    header = resp.get("header", {})
    if str(header.get("resultCode", "00")) not in ("00", "0"):
        raise HiraError(f"API 오류: {header.get('resultCode')} {header.get('resultMsg')}")
    body = resp.get("body", {}) or {}
    items = (body.get("items") or {})
    item = items.get("item", []) if isinstance(items, dict) else []
    if isinstance(item, dict):  # 결과가 1개면 리스트가 아니라 객체로 옵니다
        item = [item]
    return item, int(body.get("totalCount", 0) or 0)


def fetch_clinics(service_key: str, limit: int, sido: Optional[str], fetch: Fetcher = http_get_json) -> list[dict]:
    rows = min(100, limit)
    out: list[dict] = []
    page = 1
    while len(out) < limit:
        items, total = parse_page(fetch(build_url(service_key, page, rows, sido)))
        out.extend(items)
        if not items or len(out) >= total:
            break
        page += 1
    return out[:limit]


def _same_all_langs(value: str) -> dict:
    return {lang: value for lang in LANGS}


def _phone(raw: Any) -> str:
    return str(raw or "").strip() or "-"


def to_clinic(item: dict) -> Optional[Clinic]:
    name = str(item.get("yadmNm") or "").strip()
    ykiho = str(item.get("ykiho") or "").strip()
    if not name or not ykiho:
        return None
    digest = hashlib.sha1(ykiho.encode("utf-8")).hexdigest()
    area = " ".join(str(item.get(k) or "").strip() for k in ("sidoCdNm", "sgguCdNm", "emdongNm")).strip()
    address = str(item.get("addr") or "").strip() or area
    doctors = int(item.get("drTotCnt") or 0)
    about_ko = f"건강보험심사평가원 공공데이터 기준 성형외과 의원입니다. 의사 수: {doctors}명."
    about_en = f"Plastic surgery clinic listed in HIRA public data. Doctors: {doctors}."
    return Clinic(
        id="h" + digest[:11],
        name=_same_all_langs(name),
        area=_same_all_langs(area),
        address=_same_all_langs(address),
        phone=_phone(item.get("telno")),
        specialties=[],
        about={"ko": about_ko, "en": about_en, "ja": about_en, "zh": about_en},
        doctors=[],
        procedures=[{"key": "consult", "price": None}],
        hours_open="10:00",
        hours_close="19:00",
        closed_days=[0],
        hue=int(digest[:2], 16) * 360 // 256,
        source="hira",
        hours_estimated=True,
    )


def save(session: Session, clinics: Iterable[Clinic], replace_samples: bool) -> tuple[int, int]:
    if replace_samples:
        sample_ids = list(session.exec(select(Clinic.id).where(Clinic.source == "sample")))
        for model in (Review, Reservation):
            for row in session.exec(select(model).where(model.clinic_id.in_(sample_ids))):
                session.delete(row)
        for cid in sample_ids:
            session.delete(session.get(Clinic, cid))
        session.flush()
    added = updated = 0
    for c in clinics:
        existing = session.get(Clinic, c.id)
        if existing:
            # 공공데이터에서 오는 값만 갱신 (기존 리뷰/예약은 그대로)
            for field in ("name", "area", "address", "phone", "about"):
                setattr(existing, field, getattr(c, field))
            updated += 1
        else:
            session.add(c)
            added += 1
    session.commit()
    return added, updated


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="심평원 공공데이터에서 성형외과 목록 가져오기")
    p.add_argument("--sido", help="시도 코드 (예: 110000=서울, 210000=부산)")
    p.add_argument("--limit", type=int, default=100, help="최대 몇 곳까지 (기본 100)")
    p.add_argument("--replace-samples", action="store_true", help="가상 샘플 병원 삭제")
    p.add_argument("--dry-run", action="store_true", help="DB에 넣지 않고 출력만")
    args = p.parse_args(argv)

    key = os.getenv("HIRA_SERVICE_KEY", "").strip()
    if not key:
        print("HIRA_SERVICE_KEY 환경변수가 없어요. export HIRA_SERVICE_KEY='Decoding 키' 를 먼저 실행해 주세요.")
        return 1

    try:
        items = fetch_clinics(key, args.limit, args.sido)
    except HiraError as e:
        print(e)
        return 1
    clinics = [c for c in (to_clinic(i) for i in items) if c]
    print(f"받아온 성형외과: {len(clinics)}곳" + (f" ({SIDO.get(args.sido, args.sido)})" if args.sido else ""))
    for c in clinics[:10]:
        print(f"  - {c.name['ko']} | {c.area['ko']} | {c.phone}")
    if len(clinics) > 10:
        print(f"  ... 외 {len(clinics) - 10}곳")
    if args.dry_run:
        return 0

    create_tables()
    with Session(engine) as s:
        added, updated = save(s, clinics, args.replace_samples)
    print(f"DB 저장 완료: 새로 추가 {added}곳, 정보 갱신 {updated}곳")
    return 0


if __name__ == "__main__":
    sys.exit(main())
