from urllib.parse import parse_qs, urlsplit

from sqlalchemy import create_engine, inspect, text

from app import auth, db


def start_login(client, next_url="https://hiworld-cloud.github.io/Practice-/"):
    res = client.get("/api/auth/kakao/login", params={"next": next_url}, follow_redirects=False)
    assert res.status_code == 302
    return res


def finish_login(client, state, **params):
    res = client.get("/api/auth/kakao/callback", params={"state": state, **params}, follow_redirects=False)
    assert res.status_code == 302
    loc = urlsplit(res.headers["location"])
    return loc, {k: v[0] for k, v in parse_qs(loc.fragment).items()}


def test_login_redirects_to_kakao(client, fake_kakao):
    res = start_login(client)
    loc = urlsplit(res.headers["location"])
    q = {k: v[0] for k, v in parse_qs(loc.query).items()}
    assert loc.netloc == "kauth.kakao.com" and loc.path == "/oauth/authorize"
    assert q["client_id"] == "test-rest-key" and q["response_type"] == "code"
    assert q["redirect_uri"].endswith("/api/auth/kakao/callback")
    assert q["state"] and auth.STATE_COOKIE in res.headers["set-cookie"]


def test_login_without_kakao_key_goes_back_with_error(client, monkeypatch):
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)
    res = client.get("/api/auth/kakao/login", params={"next": "http://localhost:8000/"}, follow_redirects=False)
    assert res.headers["location"] == "http://localhost:8000/#login_error=kakao_not_configured"


def test_callback_creates_user_and_returns_token(client, fake_kakao):
    state = parse_qs(urlsplit(start_login(client).headers["location"]).query)["state"][0]
    loc, frag = finish_login(client, state, code="abc")
    assert f"{loc.scheme}://{loc.netloc}{loc.path}" == "https://hiworld-cloud.github.io/Practice-/"
    assert fake_kakao.codes == ["abc"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {frag['bb_token']}"})
    assert me.status_code == 200 and me.json()["nickname"] == "테스터"


def test_same_kakao_user_logs_into_same_account(client, login):
    a = client.get("/api/auth/me", headers=login(kakao_id=55, nickname="처음")).json()
    b = client.get("/api/auth/me", headers=login(kakao_id=55, nickname="바뀐닉")).json()
    assert a["id"] == b["id"] and b["nickname"] == "바뀐닉"


def test_callback_rejects_wrong_state(client, fake_kakao):
    start_login(client)
    _, frag = finish_login(client, "someone-elses-state", code="abc")
    assert frag == {"login_error": "invalid_state"} and fake_kakao.codes == []


def test_callback_handles_cancel_and_kakao_errors(client, fake_kakao):
    state = parse_qs(urlsplit(start_login(client).headers["location"]).query)["state"][0]
    _, frag = finish_login(client, state, error="access_denied")
    assert frag == {"login_error": "access_denied"}

    state = parse_qs(urlsplit(start_login(client).headers["location"]).query)["state"][0]
    _, frag = finish_login(client, state, code="bad")
    assert frag == {"login_error": "kakao_failed"}


def test_next_url_must_be_allowed(client, fake_kakao):
    # 모르는 사이트로는 토큰을 보내지 않고 기본 화면으로 돌아가요
    state = parse_qs(urlsplit(start_login(client, "https://evil.example.com/").headers["location"]).query)["state"][0]
    loc, frag = finish_login(client, state, code="abc")
    assert loc.netloc == "hiworld-cloud.github.io" and "bb_token" in frag
    # 내 컴퓨터(localhost)는 허락
    state = parse_qs(urlsplit(start_login(client, "http://localhost:8000/?x=1").headers["location"]).query)["state"][0]
    loc, _ = finish_login(client, state, code="abc")
    assert loc.netloc == "localhost:8000" and loc.query == "x=1"


def test_me_requires_valid_token(client, fake_kakao):
    assert client.get("/api/auth/me").status_code == 401
    expired = auth.sign({"uid": 1, "exp": 1}, "login")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    # state용으로 서명한 값은 로그인 토큰으로 못 써요
    other = auth.sign({"uid": 1, "exp": 9999999999}, "state")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {other}"}).status_code == 401


def test_old_review_table_gets_user_id_column(tmp_path):
    # 이미 Supabase에 있는 (user_id 칸이 없는) 리뷰 테이블에도 칸이 추가되는지 확인
    engine = create_engine(f"sqlite:///{tmp_path}/old.db")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE review (id INTEGER PRIMARY KEY, clinic_id VARCHAR, rating INTEGER)"))
    db.create_tables(engine)
    assert "user_id" in {c["name"] for c in inspect(engine).get_columns("review")}
    db.create_tables(engine)  # 두 번 해도 괜찮아야 해요
