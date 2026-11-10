"""공공데이터포털 '건강보험심사평가원_병원정보서비스' API에서 성형외과 병원을 불러와 Clinic 테이블에 넣습니다.

실행: (backend 폴더에서)
    python -m app.import_hira --sido 서울 --limit 20   # 처음엔 조금만 받아 보기
    python -m app.import_hira --sido 서울              # 서울 전체
    python -m app.import_hira                          # 전국 전체
    python -m app.import_hira --dry-run --limit 5      # DB에 넣지 않고 화면에만 출력

인증키는 코드에 쓰지 않고 backend/.env 파일의 HIRA_SERVICE_KEY 에서 읽습니다.
(.env 는 .gitignore 에 들어 있어서 GitHub에 올라가지 않아요. .env.example 을 복사해서 만드세요.)

같은 병원을 다시 불러오면 새로 만들지 않고 이름·주소·전화번호만 최신으로 바꿉니다.
그래서 여러 번 실행해도 안전합니다.
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterator, Optional

from sqlmodel import Session, delete, select

BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"

API_URL = "https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList"
PLASTIC_SURGERY = "08"  # 심평원 진료과목 코드: 08 = 성형외과
PAGE_SIZE = 100

# 심평원 시도 코드
SIDO_CODES = {
    "서울": "110000", "부산": "210000", "인천": "220000", "대구": "230000", "광주": "240000",
    "대전": "250000", "울산": "260000", "경기": "310000", "강원": "320000", "충북": "330000",
    "충남": "340000", "전북": "350000", "전남": "360000", "경북": "370000", "경남": "380000",
    "제주": "390000", "세종": "410000",
}

SAMPLE_IDS = [f"c0{i}" for i in range(1, 9)]  # seed_data.json 의 가상 병원 8곳


class ImportError_(Exception):
    """사용자에게 그대로 보여 줄 오류 (한국어 안내 포함)."""


# ---------- 설정 읽기 ----------

def load_env_file(path: Path = ENV_FILE) -> None:
    """KEY=VALUE 형식의 .env 파일을 읽어 환경변수로 넣습니다. 이미 있는 환경변수는 덮어쓰지 않아요."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def get_service_key() -> str:
    key = os.getenv("HIRA_SERVICE_KEY", "").strip()
    if not key or key == "여기에_인증키_붙여넣기":
        raise ImportError_(
            "인증키가 없어요.\n"
            "  1) backend/.env.example 파일을 복사해서 backend/.env 를 만들고\n"
            "  2) HIRA_SERVICE_KEY= 뒤에 공공데이터포털의 '일반 인증키(Decoding)'를 붙여 넣은 뒤\n"
            "  3) 다시 실행해 주세요."
        )
    # Encoding 키(%2B 같은 글자가 들어 있음)를 넣었어도 동작하도록 Decoding 형태로 바꿔 둡니다.
    if "%" in key:
        key = urllib.parse.unquote(key)
    return key


# ---------- API 호출 ----------

def fetch_page(service_key: str, page: int, sido_code: Optional[str] = None,
               rows: int = PAGE_SIZE, url: Optional[str] = None) -> dict:
    params = {
        "ServiceKey": service_key,
        "pageNo": page,
        "numOfRows": rows,
        "dgsbjtCd": PLASTIC_SURGERY,
        "_type": "json",
    }
    if sido_code:
        params["sidoCd"] = sido_code
    full_url = f"{url or os.getenv('HIRA_API_URL') or API_URL}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(full_url, timeout=30) as resp:
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise ImportError_(
            f"API 서버가 오류를 돌려줬어요 (HTTP {e.code}).\n"
            "  승인 직후라면 키가 동작하기까지 1~2시간 걸릴 수 있어요. 잠시 뒤 다시 해 보세요."
        ) from e
    except urllib.error.URLError as e:
        raise ImportError_(f"API 서버에 연결하지 못했어요: {e.reason}\n  인터넷 연결을 확인해 주세요.") from e
    return parse_response(text)


def parse_response(text: str) -> dict:
    """API 응답(JSON)에서 body 부분을 꺼냅니다. 키가 틀리면 XML 오류가 오기 때문에 그것도 알아봐요."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        if "SERVICE_KEY_IS_NOT_REGISTERED" in text or "SERVICE KEY IS NOT REGISTERED" in text:
            raise ImportError_(
                "등록되지 않은 인증키라고 나와요.\n"
                "  - 승인 직후라면 1~2시간 뒤에 다시 해 보세요.\n"
                "  - 마이페이지의 '일반 인증키(Decoding)'를 정확히 복사했는지 확인해 주세요."
            )
        if "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in text:
            raise ImportError_("오늘 쓸 수 있는 호출 횟수를 다 썼어요. 내일 다시 해 주세요.")
        raise ImportError_(f"API 응답을 읽지 못했어요. 응답 앞부분:\n{text[:300]}")

    resp = data.get("response", data)
    header = resp.get("header", {})
    code = str(header.get("resultCode", "00"))
    if code not in ("00", "0"):
        raise ImportError_(f"API 오류 {code}: {header.get('resultMsg', '')}")
    return resp.get("body", {}) or {}


def items_of(body: dict) -> list[dict]:
    items = body.get("items") or {}
    if not isinstance(items, dict):  # 결과가 없으면 items 가 "" 로 와요
        return []
    item = items.get("item") or []
    return [item] if isinstance(item, dict) else list(item)  # 1건이면 리스트가 아니라 dict 로 와요


def fetch_all(service_key: str, sido_code: Optional[str] = None, limit: Optional[int] = None,
              fetch=fetch_page) -> Iterator[dict]:
    """페이지를 넘기며 병원을 하나씩 돌려줍니다."""
    page, seen = 1, 0
    rows = PAGE_SIZE if limit is None else max(1, min(PAGE_SIZE, limit))  # 페이지마다 같은 크기로 받아야 순서가 안 꼬여요
    while True:
        body = fetch(service_key, page, sido_code, rows)
        items = items_of(body)
        total = int(body.get("totalCount") or 0)
        if page == 1:
            print(f"API에서 찾은 성형외과 진료 병원: {total}곳")
        want = total if limit is None else min(total, limit)
        pages = max(1, -(-want // rows))  # 올림 나눗셈
        print(f"  받는 중... {page}/{pages} 페이지", flush=True)
        for it in items:
            yield it
            seen += 1
            if limit is not None and seen >= limit:
                return
        if not items or seen >= total:
            return
        page += 1


# ---------- DB에 맞게 바꾸기 ----------

def clinic_id_for(item: dict) -> str:
    """심평원 암호화 요양기호(ykiho)로 짧고 변하지 않는 ID를 만듭니다."""
    source = item.get("ykiho") or f"{item.get('yadmNm')}|{item.get('addr')}"
    return "hira-" + hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]


def to_clinic_fields(item: dict) -> dict[str, Any]:
    name = (item.get("yadmNm") or "").strip()
    addr = (item.get("addr") or "").strip()
    area = " ".join(x for x in (item.get("sgguCdNm"), item.get("emdongNm")) if x).strip() or item.get("sidoCdNm", "")
    kind = item.get("clCdNm") or ""
    doctors = item.get("drTotCnt")
    about_ko = " · ".join(x for x in (
        kind,
        f"의사 {doctors}명" if doctors not in (None, "") else "",
        "건강보험심사평가원 공공데이터 기준 정보예요. 진료 시간과 시술은 병원에 확인해 주세요.",
    ) if x)
    about_en = "Public data from HIRA (Health Insurance Review & Assessment Service). Please check hours and procedures with the clinic."
    # 다른 언어 번역은 아직 없어서 이름·주소는 한국어를 그대로 씁니다. 화면은 한국어로 대신 보여 줘요.
    same = lambda s: {"ko": s, "en": s, "ja": s, "zh": s}  # noqa: E731
    return {
        "name": same(name),
        "area": same(area),
        "address": same(addr),
        "phone": (item.get("telno") or "").strip(),
        "about": {"ko": about_ko, "en": about_en, "ja": about_en, "zh": about_en},
    }


def new_clinic(clinic_id: str, fields: dict[str, Any]):
    from .models import Clinic

    return Clinic(
        id=clinic_id,
        specialties=[],              # 공공데이터에는 '눈/코' 같은 세부 분야가 없어요
        doctors=[],
        procedures=[{"key": "consultation", "price": 0}],  # 시술·가격은 아직 몰라서 '상담'만
        hours_open="10:00",          # 기본값. 병원별 진료 시간은 다음 단계에서
        hours_close="19:00",
        closed_days=[0],
        hue=int(clinic_id[-4:], 16) % 360,
        **fields,
    )


def upsert(session: Session, items) -> tuple[int, int]:
    from .models import Clinic

    added = updated = 0
    for item in items:
        if not item.get("yadmNm"):
            continue
        cid = clinic_id_for(item)
        fields = to_clinic_fields(item)
        existing = session.get(Clinic, cid)
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
            updated += 1
        else:
            session.add(new_clinic(cid, fields))
            added += 1
    session.commit()
    return added, updated


def remove_samples(session: Session) -> int:
    from .models import Clinic, Reservation, Review

    ids = [c.id for c in session.exec(select(Clinic).where(Clinic.id.in_(SAMPLE_IDS))).all()]
    if ids:
        session.exec(delete(Review).where(Review.clinic_id.in_(ids)))
        session.exec(delete(Reservation).where(Reservation.clinic_id.in_(ids)))
        session.exec(delete(Clinic).where(Clinic.id.in_(ids)))
        session.commit()
    return len(ids)


# ---------- 실행 ----------

def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="공공데이터 API에서 성형외과 목록을 불러와 DB에 넣습니다.")
    p.add_argument("--sido", help="지역만 받기. 예: 서울, 부산, 경기 (생략하면 전국)")
    p.add_argument("--limit", type=int, help="최대 몇 곳까지 받을지 (처음 테스트할 때 20 정도 추천)")
    p.add_argument("--dry-run", action="store_true", help="DB에 넣지 않고 받아온 내용만 출력")
    p.add_argument("--remove-samples", action="store_true", help="가상 샘플 병원 8곳(과 그 리뷰·예약)을 지움")
    args = p.parse_args(argv)

    load_env_file()
    try:
        sido_code = None
        if args.sido:
            sido_code = SIDO_CODES.get(args.sido.strip())
            if not sido_code:
                raise ImportError_(f"모르는 지역이에요: {args.sido}\n  쓸 수 있는 값: {', '.join(SIDO_CODES)}")
        key = get_service_key()
        items = fetch_all(key, sido_code, args.limit)

        if args.dry_run:
            n = 0
            for it in items:
                f = to_clinic_fields(it)
                print(f"- {f['name']['ko']} | {f['address']['ko']} | {f['phone']}")
                n += 1
            print(f"(dry-run) {n}곳을 받아왔어요. DB에는 넣지 않았어요.")
            return 0

        from .db import create_tables, engine

        create_tables()
        with Session(engine) as s:
            added, updated = upsert(s, items)  # 다 받은 뒤 한 번에 저장해요
            print(f"DB 저장 완료: 새로 추가 {added}곳, 정보 갱신 {updated}곳")
            if args.remove_samples:
                print(f"가상 샘플 병원 {remove_samples(s)}곳을 지웠어요.")
    except ImportError_ as e:
        print(f"\n[오류] {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
