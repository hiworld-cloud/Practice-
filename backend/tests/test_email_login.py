from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect, text

from app import db, email_login


@pytest.fixture(autouse=True)
def _reset():
    email_login.reset_fails()


def signup(client, email="me@example.com", password="secret123", nickname="재하"):
    return client.post("/api/auth/signup", json={"email": email, "password": password, "nickname": nickname})


def bearer(res):
    return {"Authorization": f"Bearer {res.json()['token']}"}


def test_signup_logs_in_and_can_write_review(client):
    res = signup(client)
    assert res.status_code == 201
    assert res.json()["user"]["nickname"] == "재하"
    assert client.get("/api/auth/me", headers=bearer(res)).json()["nickname"] == "재하"
    review = client.post("/api/clinics/c01/reviews", json={"rating": 5}, headers=bearer(res))
    assert review.status_code == 201 and review.json()["nick"] == "재하"


def test_signup_rules(client):
    def code(**kw):
        r = signup(client, **kw)
        return r.status_code, r.json()["detail"]["code"]

    assert code(email="not-an-email") == (422, "invalid_email")
    assert code(password="short1") == (422, "weak_password")
    assert code(password="12345678") == (422, "weak_password")  # 숫자만
    assert code(password="abcdefgh") == (422, "weak_password")  # 글자만
    assert code(nickname="  ") == (422, "nickname_required")
    assert signup(client).status_code == 201
    assert code(email="ME@Example.com ") == (409, "email_taken")  # 대소문자·공백 달라도 같은 이메일


def test_password_is_not_stored_as_is(client):
    signup(client, password="secret123")
    with db.engine.connect() as conn:
        stored = conn.execute(text("SELECT password_hash FROM app_user WHERE email='me@example.com'")).scalar()
    assert "secret123" not in stored and stored.startswith("scrypt$")
    assert email_login.verify_password("secret123", stored)
    assert not email_login.verify_password("secret124", stored)


def test_login(client):
    signup(client)
    ok = client.post("/api/auth/login", json={"email": "Me@example.com", "password": "secret123"})
    assert ok.status_code == 200 and ok.json()["user"]["nickname"] == "재하"
    assert client.get("/api/auth/me", headers=bearer(ok)).status_code == 200

    wrong_pw = client.post("/api/auth/login", json={"email": "me@example.com", "password": "nope12345"})
    no_user = client.post("/api/auth/login", json={"email": "who@example.com", "password": "secret123"})
    # 이메일이 없는 건지 비밀번호가 틀린 건지 구분되지 않아야 해요
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json() == {"detail": {"code": "wrong_credentials"}}


def test_login_locks_after_five_failures(client):
    signup(client)
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": "me@example.com", "password": "bad-pass-1"}).status_code == 401
    locked = client.post("/api/auth/login", json={"email": "me@example.com", "password": "secret123"})
    assert locked.status_code == 429 and locked.json()["detail"]["code"] == "too_many_attempts"


def test_kakao_user_cannot_be_logged_into_with_password(client, login):
    login(kakao_id=777, nickname="카카오")
    res = client.post("/api/auth/login", json={"email": "", "password": "secret123"})
    assert res.status_code == 401


def test_old_user_table_allows_email_only_users(tmp_path):
    # 카카오 전용으로 만들었던 예전 app_user 표(kakao_id 필수, email 칸 없음)를 고쳐 주는지 확인
    engine = create_engine(f"sqlite:///{tmp_path}/old.db")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE app_user (id INTEGER PRIMARY KEY, kakao_id BIGINT NOT NULL, "
                          "nickname VARCHAR NOT NULL, created_at DATETIME NOT NULL, last_login_at DATETIME NOT NULL)"))
        conn.execute(text("CREATE UNIQUE INDEX ix_app_user_kakao_id ON app_user (kakao_id)"))
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(text("INSERT INTO app_user VALUES (1, 55, '기존회원', :t, :t)"), {"t": now})
    db.create_tables(engine)
    db.create_tables(engine)  # 두 번 해도 괜찮아야 해요
    cols = {c["name"]: c for c in inspect(engine).get_columns("app_user")}
    assert cols["kakao_id"]["nullable"] and "email" in cols and "password_hash" in cols
    with engine.begin() as conn:
        assert conn.execute(text("SELECT nickname FROM app_user WHERE kakao_id=55")).scalar() == "기존회원"
        conn.execute(text("INSERT INTO app_user (email, nickname, created_at, last_login_at) "
                          "VALUES ('a@b.co', 'x', :t, :t)"), {"t": now})
