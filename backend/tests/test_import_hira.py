"""공공데이터 가져오기 테스트. 실제 API 대신 같은 모양의 가짜 응답을 씁니다."""
from urllib.parse import parse_qs, urlparse

import pytest
from sqlmodel import Session, select

from app import db
from app.import_hira import HiraError, build_url, fetch_clinics, parse_page, save, to_clinic
from app.models import Clinic, Review
from app.seed import seed


def item(n):
    return {
        "yadmNm": f"테스트{n}성형외과의원", "ykiho": f"KEY{n:04d}", "addr": f"서울특별시 강남구 테스트로 {n}",
        "telno": f"02-000-{n:04d}", "sidoCdNm": "서울", "sgguCdNm": "강남구", "emdongNm": "신사동", "drTotCnt": 2,
    }


def page(items, total, code="00"):
    return {"response": {"header": {"resultCode": code, "resultMsg": "NORMAL SERVICE."},
                         "body": {"items": {"item": items}, "totalCount": total}}}


def test_build_url_filters_plastic_surgery_clinics():
    q = parse_qs(urlparse(build_url("k+ey/=", 2, 50, "110000")).query)
    assert q["dgsbjtCd"] == ["08"] and q["clCd"] == ["31"] and q["sidoCd"] == ["110000"]
    assert q["serviceKey"] == ["k+ey/="] and q["pageNo"] == ["2"] and q["_type"] == ["json"]


def test_parse_page_handles_single_item_empty_and_errors():
    assert parse_page(page(item(1), 1)) == ([item(1)], 1)
    assert parse_page({"response": {"header": {"resultCode": "00"}, "body": {"items": "", "totalCount": 0}}}) == ([], 0)
    with pytest.raises(HiraError):
        parse_page(page([], 0, code="30"))


def test_fetch_clinics_pages_until_limit():
    calls = []

    def fake(url):
        n = int(parse_qs(urlparse(url).query)["pageNo"][0])
        calls.append(n)
        return page([item(i) for i in range((n - 1) * 100, n * 100)], 250)

    assert len(fetch_clinics("k", 150, None, fetch=fake)) == 150
    assert calls == [1, 2]


def test_to_clinic_maps_fields_and_marks_estimates():
    c = to_clinic(item(7))
    assert c.name == {"ko": "테스트7성형외과의원", "en": "테스트7성형외과의원", "ja": "테스트7성형외과의원", "zh": "테스트7성형외과의원"}
    assert c.area["ko"] == "서울 강남구 신사동" and c.phone == "02-000-0007"
    assert c.source == "hira" and c.hours_estimated and c.procedures == [{"key": "consult", "price": None}]
    assert to_clinic(item(7)).id == c.id  # 같은 병원은 항상 같은 id
    assert to_clinic({"yadmNm": "", "ykiho": "x"}) is None


def test_save_adds_updates_and_replaces_samples(client):
    with Session(db.engine) as s:
        added, updated = save(s, [to_clinic(item(1)), to_clinic(item(2))], replace_samples=True)
        assert (added, updated) == (2, 0)
        assert {c.source for c in s.exec(select(Clinic))} == {"hira"}
        assert s.exec(select(Review)).all() == []  # 샘플 리뷰도 같이 삭제
        changed = to_clinic(item(1))
        changed.phone = "02-999-9999"
        assert save(s, [changed], replace_samples=False) == (0, 1)
        assert s.get(Clinic, changed.id).phone == "02-999-9999"
        assert seed(s) == 0  # 서버를 다시 켜도 샘플이 되살아나지 않음


def test_public_clinic_works_in_api(client, guest):
    with Session(db.engine) as s:
        save(s, [to_clinic(item(3))], replace_samples=False)
    cid = to_clinic(item(3)).id
    c = client.get(f"/api/clinics/{cid}").json()
    assert c["source"] == "hira" and c["hoursEstimated"] is True and c["count"] == 0
    from tests.test_api import next_open_day
    r = client.post("/api/reservations", headers=guest, json={
        "clinicId": cid, "name": "홍길동", "phone": "010-0000-0000", "procedure": "consult",
        "date": next_open_day([0]), "time": "10:00"})
    assert r.status_code == 201, r.text
