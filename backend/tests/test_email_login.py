import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

import pytest
from sqlalchemy import create_engine, inspect, text

from app import db, email_login, mailer


@pytest.fixture(autouse=True)
def _reset():
    email_login.reset_fails()


@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    """진짜 메일 대신 보낸 메일을 이 목록에 모아요."""
    sent = []
    monkeypatch.setattr(mailer, "send_mail", lambda to, subject, text, html: sent.append(
        {"to": to, "subject": subject, "text": text, "html": html}) or True)
    return sent


def link_token(mail, name):
    """메일 본문의 링크에서 #verify_token=... / #reset_token=... 값을 꺼내요."""
    link = next(w for w in mail["text"].split() if f"#{name}=" in w)
    return urlsplit(link).fragment.split("=", 1)[1]


def signup(client, email="me@example.com", password="secret123", nickname="재하"):
    return client.post("/api/auth/signup", json={"email": email, "password": password, "nickname": nickname})


def verified_signup(client, outbox, **kw):
    """가입 + 메일 속 링크로 인증까지 끝내고 로그인 응답을 돌려줘요."""
    assert signup(client, **kw).status_code == 201
    return client.post("/api/auth/verify-email", json={"token": link_token(outbox[-1], "verify_token")})


def bearer(res):
    return {"Authorization": f"Bearer {res.json()['token']}"}


def test_signup_sends_verify_mail_and_does_not_log_in(client, outbox):
    res = signup(client)
    assert res.status_code == 201
    assert res.json() == {"verify_sent": True, "email": "me@example.com"}
    assert "token" not in res.json()
    assert len(outbox) == 1 and outbox[0]["to"] == "me@example.com"
    assert "secret123" not in outbox[0]["text"] + outbox[0]["html"]  # 비밀번호는 절대 메일에 안 넣어요
    # 인증 전에는 비밀번호가 맞아도 로그인 안 됨
    res = client.post("/api/auth/login", json={"email": "me@example.com", "password": "secret123"})
    assert res.status_code == 403 and res.json()["detail"]["code"] == "email_not_verified"


def test_verify_link_logs_in_and_can_write_review(client, outbox):
    res = verified_signup(client, outbox)
    assert res.status_code == 200 and res.json()["user"]["nickname"] == "재하"
    assert client.get("/api/auth/me", headers=bearer(res)).json()["nickname"] == "재하"
    review = client.post("/api/clinics/c01/reviews", json={"rating": 5}, headers=bearer(res))
    assert review.status_code == 201 and review.json()["nick"] == "재하"
    # 같은 링크를 또 누르면 "이미 인증됨"만 알려 주고 로그인 토큰은 안 줘요
    again = client.post("/api/auth/verify-email", json={"token": link_token(outbox[0], "verify_token")})
    assert again.json() == {"already": True}
    ok = client.post("/api/auth/login", json={"email": "me@example.com", "password": "secret123"})
    assert ok.status_code == 200


def test_verify_link_rejects_bad_or_expired_tokens(client, outbox, monkeypatch):
    signup(client)
    token = link_token(outbox[0], "verify_token")
    bad = client.post("/api/auth/verify-email", json={"token": token[:-3] + "abc"})
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "invalid_link"
    # 메일 링크용 토큰으로 로그인 흉내를 낼 수 없어요 (용도가 다르게 서명돼요)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + email_login.VERIFY_TTL + 5)
    expired = client.post("/api/auth/verify-email", json={"token": token})
    assert expired.status_code == 400


def test_resend_verify_mail(client, outbox):
    signup(client)
    # 방금 가입하면서 보냈으니 1분 안에는 다시 안 보내요
    assert client.post("/api/auth/verify-email/resend", json={"email": "me@example.com"}).json() == {"ok": True}
    assert len(outbox) == 1
    email_login._mail_sent.clear()  # 1분이 지났다고 치고
    client.post("/api/auth/verify-email/resend", json={"email": "ME@example.com"})
    assert len(outbox) == 2
    # 가입 안 된 이메일도 똑같이 답해요 (가입 여부를 알 수 없게). 메일은 안 보내요.
    assert client.post("/api/auth/verify-email/resend", json={"email": "who@example.com"}).json() == {"ok": True}
    assert len(outbox) == 2


def test_password_reset_flow(client, outbox):
    verified_signup(client, outbox)
    outbox.clear()
    res = client.post("/api/auth/password-reset/request", json={"email": "Me@Example.com"})
    assert res.json() == {"ok": True} and len(outbox) == 1
    assert "secret123" not in outbox[0]["text"]  # 원래 비밀번호는 보내지 않아요 (우리도 몰라요)
    token = link_token(outbox[0], "reset_token")

    weak = client.post("/api/auth/password-reset/confirm", json={"token": token, "password": "short"})
    assert weak.status_code == 422 and weak.json()["detail"]["code"] == "weak_password"
    done = client.post("/api/auth/password-reset/confirm", json={"token": token, "password": "newpass456"})
    assert done.status_code == 200 and client.get("/api/auth/me", headers=bearer(done)).status_code == 200

    # 새 비밀번호로만 로그인돼요
    assert client.post("/api/auth/login", json={"email": "me@example.com", "password": "secret123"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "me@example.com", "password": "newpass456"}).status_code == 200
    # 같은 링크는 두 번 못 써요
    again = client.post("/api/auth/password-reset/confirm", json={"token": token, "password": "other789x"})
    assert again.status_code == 400 and again.json()["detail"]["code"] == "invalid_link"


def test_password_reset_does_not_reveal_accounts(client, outbox, login):
    login(kakao_id=777, nickname="카카오")  # 카카오 회원은 비밀번호가 없어요
    assert client.post("/api/auth/password-reset/request", json={"email": "nobody@example.com"}).json() == {"ok": True}
    assert outbox == []
    verified_signup(client, outbox)
    outbox.clear()
    client.post("/api/auth/password-reset/request", json={"email": "me@example.com"})
    client.post("/api/auth/password-reset/request", json={"email": "me@example.com"})  # 1분 안에 또 → 안 보냄
    assert len(outbox) == 1


def test_password_reset_verifies_email_and_unlocks(client, outbox):
    # 인증 안 한 채로 비밀번호도 잊고, 5번 틀려서 잠긴 사람
    signup(client)
    for _ in range(5):
        client.post("/api/auth/login", json={"email": "me@example.com", "password": "bad-pass-1"})
    client.post("/api/auth/password-reset/request", json={"email": "me@example.com"})
    token = link_token(outbox[-1], "reset_token")
    assert client.post("/api/auth/password-reset/confirm", json={"token": token, "password": "newpass456"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "me@example.com", "password": "newpass456"}).status_code == 200


def test_reset_link_expires(client, outbox, monkeypatch):
    verified_signup(client, outbox)
    client.post("/api/auth/password-reset/request", json={"email": "me@example.com"})
    token = link_token(outbox[-1], "reset_token")
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + email_login.RESET_TTL + 5)
    res = client.post("/api/auth/password-reset/confirm", json={"token": token, "password": "newpass456"})
    assert res.status_code == 400


def test_mail_links_point_to_frontend(client, outbox, monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://hiworld-cloud.github.io/Practice-/")
    signup(client)
    assert "https://hiworld-cloud.github.io/Practice-/#verify_token=" in outbox[0]["text"]


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


def test_login(client, outbox):
    verified_signup(client, outbox)
    ok = client.post("/api/auth/login", json={"email": "Me@example.com", "password": "secret123"})
    assert ok.status_code == 200 and ok.json()["user"]["nickname"] == "재하"
    assert client.get("/api/auth/me", headers=bearer(ok)).status_code == 200

    wrong_pw = client.post("/api/auth/login", json={"email": "me@example.com", "password": "nope12345"})
    no_user = client.post("/api/auth/login", json={"email": "who@example.com", "password": "secret123"})
    # 이메일이 없는 건지 비밀번호가 틀린 건지 구분되지 않아야 해요
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json() == {"detail": {"code": "wrong_credentials"}}


def test_login_locks_after_five_failures(client, outbox):
    verified_signup(client, outbox)
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
    assert cols["kakao_id"]["nullable"] and "email" in cols and "password_hash" in cols and "email_verified" in cols
    with engine.begin() as conn:
        assert conn.execute(text("SELECT nickname FROM app_user WHERE kakao_id=55")).scalar() == "기존회원"
        conn.execute(text("INSERT INTO app_user (email, nickname, created_at, last_login_at) "
                          "VALUES ('a@b.co', 'x', :t, :t)"), {"t": now})
        assert conn.execute(text("SELECT email_verified FROM app_user WHERE email='a@b.co'")).scalar() in (0, False)


def test_email_verified_column_added_to_existing_table(tmp_path):
    # 이메일 로그인까지는 있었지만 email_verified 칸이 없는 예전 표 → 칸을 추가하고 기존 회원은 "미인증"
    engine = create_engine(f"sqlite:///{tmp_path}/prev.db")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE app_user (id INTEGER PRIMARY KEY, kakao_id BIGINT, email VARCHAR(254), "
                          "password_hash VARCHAR, nickname VARCHAR NOT NULL, created_at DATETIME NOT NULL, "
                          "last_login_at DATETIME NOT NULL)"))
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(text("INSERT INTO app_user VALUES (1, NULL, 'old@b.co', 'scrypt$x', '예전회원', :t, :t)"), {"t": now})
    db.create_tables(engine)
    with engine.begin() as conn:
        assert conn.execute(text("SELECT email_verified FROM app_user WHERE id=1")).scalar() in (0, False)
