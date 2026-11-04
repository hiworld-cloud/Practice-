from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def next_open_day(closed_days, start=1):
    d = datetime.now(KST).date() + timedelta(days=start)
    while (d.isoweekday() % 7) in closed_days:
        d += timedelta(days=1)
    return d.isoformat()


def next_closed_day(closed_day):
    d = datetime.now(KST).date() + timedelta(days=1)
    while (d.isoweekday() % 7) != closed_day:
        d += timedelta(days=1)
    return d.isoformat()


def booking(**over):
    body = {"clinicId": "c01", "name": "홍길동", "phone": "010-0000-0000",
            "procedure": "doubleEyelid", "date": next_open_day([0]), "time": "10:00"}
    body.update(over)
    return body


def test_health(client):
    assert client.get("/api/health").json() == {"ok": True}


def test_list_clinics_has_seed_data_and_ratings(client):
    clinics = client.get("/api/clinics").json()
    assert len(clinics) == 8
    c01 = next(c for c in clinics if c["id"] == "c01")
    assert c01["name"]["ko"] == "서울하늘 성형외과"
    assert c01["hours"] == {"open": "10:00", "close": "19:00"}
    assert c01["count"] == 2 and c01["rating"] == 4.5  # 샘플 리뷰 5점 + 4점


def test_unknown_clinic_is_404(client):
    assert client.get("/api/clinics/nope").status_code == 404


def test_add_review_updates_average_and_marks_mine(client, guest):
    res = client.post("/api/clinics/c06/reviews", json={"rating": 4, "nick": "me", "text": "좋아요"}, headers=guest)
    assert res.status_code == 201
    c06 = client.get("/api/clinics/c06").json()
    assert c06["count"] == 1 and c06["rating"] == 4.0
    reviews = client.get("/api/clinics/c06/reviews", headers=guest).json()
    assert reviews[0]["mine"] is True
    other = client.get("/api/clinics/c06/reviews", headers={"X-Guest-Id": "someone-else-01"}).json()
    assert other[0]["mine"] is False


def test_review_rejects_bad_rating_and_missing_guest(client, guest):
    assert client.post("/api/clinics/c01/reviews", json={"rating": 6}, headers=guest).status_code == 422
    assert client.post("/api/clinics/c01/reviews", json={"rating": 5}).status_code == 400


def test_reservation_flow(client, guest):
    res = client.post("/api/reservations", json=booking(), headers=guest)
    assert res.status_code == 201, res.text
    rid = res.json()["id"]

    mine = client.get("/api/reservations/me", headers=guest).json()
    assert [r["id"] for r in mine] == [rid]
    assert client.get("/api/reservations/me", headers={"X-Guest-Id": "someone-else-01"}).json() == []

    taken = client.get("/api/clinics/c01/taken-slots", params={"date": booking()["date"]}).json()
    assert taken == ["10:00"]

    # 다른 사람이 같은 시간에 예약하면 거절
    dup = client.post("/api/reservations", json=booking(), headers={"X-Guest-Id": "someone-else-01"})
    assert dup.status_code == 409 and dup.json()["detail"]["code"] == "slot_taken"

    # 다른 사람은 내 예약을 취소할 수 없음
    assert client.delete(f"/api/reservations/{rid}", headers={"X-Guest-Id": "someone-else-01"}).status_code == 404
    assert client.delete(f"/api/reservations/{rid}", headers=guest).status_code == 204
    assert client.get("/api/reservations/me", headers=guest).json() == []


def test_reservation_validation(client, guest):
    def code(**over):
        r = client.post("/api/reservations", json=booking(**over), headers=guest)
        return r.status_code, r.json().get("detail", {}).get("code") if r.status_code != 201 else None

    assert code(date=next_closed_day(0)) == (422, "clinic_closed")
    assert code(time="09:00") == (422, "invalid_time")
    assert code(time="18:30") == (201, None)  # 마지막 슬롯은 가능
    assert code(time="19:00") == (422, "invalid_time")
    assert code(procedure="vline") == (422, "invalid_procedure")
    yesterday = (datetime.now(KST).date() - timedelta(days=1)).isoformat()
    assert code(date=yesterday) == (422, "date_out_of_range")
    assert code(date="2026-13-40") == (422, "invalid_date")


def test_site_is_served_in_server_mode(client):
    assert "BeautyBook" in client.get("/").text
    assert client.get("/js/config.js").text.strip() == 'window.BEAUTYBOOK_API_BASE = "";'
    assert client.get("/js/app.js").status_code == 200
    assert client.get("/backend/beautybook.db").status_code == 404
