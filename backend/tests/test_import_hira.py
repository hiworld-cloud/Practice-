"""공공데이터 불러오기 스크립트 테스트. 진짜 API는 부르지 않고 가짜 응답으로 확인해요."""
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlmodel import Session, SQLModel, select

from app import db, import_hira
from app.models import Clinic, Review


def next_open_day():
    d = datetime.now(ZoneInfo("Asia/Seoul")).date() + timedelta(days=1)
    while d.isoweekday() == 7:  # 일요일 휴진
        d += timedelta(days=1)
    return d.isoformat()


def hira_item(n, **over):
    item = {"ykiho": f"ykiho-{n}", "yadmNm": f"테스트성형외과의원{n}", "addr": f"서울특별시 강남구 테헤란로 {n}",
            "telno": f"02-123-{n:04d}", "clCdNm": "의원", "sidoCdNm": "서울", "sgguCdNm": "강남구",
            "emdongNm": "역삼동", "drTotCnt": 2}
    item.update(over)
    return item


def fake_fetch(all_items):
    calls = []

    def fetch(key, page, sido, rows):
        calls.append((page, sido, rows))
        start = (page - 1) * rows
        return {"totalCount": len(all_items), "items": {"item": all_items[start:start + rows]}}

    fetch.calls = calls
    return fetch


@pytest.fixture
def session():
    SQLModel.metadata.drop_all(db.engine)
    db.create_tables()
    with Session(db.engine) as s:
        yield s


def test_parse_response_json_and_single_item():
    text = json.dumps({"response": {"header": {"resultCode": "00"},
                                    "body": {"totalCount": 1, "items": {"item": hira_item(1)}}}})
    body = import_hira.parse_response(text)
    assert [i["yadmNm"] for i in import_hira.items_of(body)] == ["테스트성형외과의원1"]
    assert import_hira.items_of({"items": ""}) == []


def test_parse_response_unregistered_key_gives_korean_hint():
    xml = "<OpenAPI_ServiceResponse><returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg></OpenAPI_ServiceResponse>"
    with pytest.raises(import_hira.ImportError_, match="등록되지 않은 인증키"):
        import_hira.parse_response(xml)


def test_fetch_all_pages_and_limit():
    items = [hira_item(i) for i in range(250)]
    fetch = fake_fetch(items)
    got = list(import_hira.fetch_all("k", "110000", fetch=fetch))
    assert len(got) == 250 and len({g["ykiho"] for g in got}) == 250
    assert [c[0] for c in fetch.calls] == [1, 2, 3]

    fetch = fake_fetch(items)
    got = list(import_hira.fetch_all("k", None, limit=150, fetch=fetch))
    assert len({g["ykiho"] for g in got}) == 150  # 페이지가 겹쳐서 중복되면 안 돼요


def test_upsert_adds_then_updates_without_duplicates(session):
    assert import_hira.upsert(session, [hira_item(1), hira_item(2)]) == (2, 0)
    assert import_hira.upsert(session, [hira_item(1, telno="02-999-9999")]) == (0, 1)
    clinics = session.exec(select(Clinic)).all()
    assert len(clinics) == 2
    c = session.get(Clinic, import_hira.clinic_id_for(hira_item(1)))
    assert c.phone == "02-999-9999"
    assert c.name["ko"] == "테스트성형외과의원1" and c.area["ko"] == "강남구 역삼동"
    assert c.procedures == [{"key": "consultation", "price": 0}]


def test_remove_samples(session):
    from app.seed import seed

    seed(session)
    import_hira.upsert(session, [hira_item(1)])
    assert import_hira.remove_samples(session) == 8
    assert [c.id for c in session.exec(select(Clinic)).all()] == [import_hira.clinic_id_for(hira_item(1))]
    assert session.exec(select(Review)).all() == []


def test_missing_key_message(monkeypatch):
    monkeypatch.delenv("HIRA_SERVICE_KEY", raising=False)
    with pytest.raises(import_hira.ImportError_, match="인증키가 없어요"):
        import_hira.get_service_key()
    monkeypatch.setenv("HIRA_SERVICE_KEY", "abc%2Bdef%3D%3D")  # Encoding 키를 넣어도
    assert import_hira.get_service_key() == "abc+def=="


def test_imported_clinic_is_bookable_via_api(client, guest):
    with Session(db.engine) as s:
        import_hira.upsert(s, [hira_item(7)])
    cid = import_hira.clinic_id_for(hira_item(7))
    assert any(c["id"] == cid for c in client.get("/api/clinics").json())
    r = client.post("/api/reservations", headers=guest, json={
        "clinicId": cid, "name": "홍길동", "phone": "010-0000-0000", "procedure": "consultation",
        "date": next_open_day(), "time": "10:00"})
    assert r.status_code == 201, r.text
