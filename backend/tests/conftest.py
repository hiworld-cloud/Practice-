import os
import tempfile

import pytest

# 테스트는 실제 DB 파일을 건드리지 않도록 임시 SQLite 파일을 씁니다 (app import 전에 설정).
# PostgreSQL로도 확인하고 싶으면 TEST_DATABASE_URL 에 "테스트용" DB 주소를 넣으세요. (테이블을 지웠다 다시 만들어요!)
_tmpdir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{_tmpdir}/test.db"

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from app import db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client():
    SQLModel.metadata.drop_all(db.engine)
    with TestClient(app) as c:  # 시작할 때 테이블 생성 + 샘플 데이터 입력
        yield c


@pytest.fixture
def guest():
    return {"X-Guest-Id": "guest-test-0001"}


@pytest.fixture
def fake_kakao(monkeypatch):
    """진짜 카카오 서버 대신 쓰는 가짜. kakao.profile 을 바꾸면 다른 사람으로 로그인돼요."""
    from app import auth

    class Fake:
        profile = {"kakao_id": 1234567890123, "nickname": "테스터"}
        codes = []

    def exchange(code):
        if code == "bad":
            raise ValueError("kakao_token_failed")
        Fake.codes.append(code)
        return "kakao-access-token"

    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-rest-key")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("FRONTEND_URL", "https://hiworld-cloud.github.io/Practice-/")
    monkeypatch.setattr(auth, "kakao_exchange_code", exchange)
    monkeypatch.setattr(auth, "kakao_fetch_profile", lambda token: dict(Fake.profile))
    return Fake


@pytest.fixture
def login(client, fake_kakao):
    """카카오 로그인 과정을 끝까지 거쳐서 Authorization 헤더를 돌려줘요."""
    from urllib.parse import parse_qs, urlsplit

    def do(kakao_id=1234567890123, nickname="테스터", next_url="https://hiworld-cloud.github.io/Practice-/"):
        fake_kakao.profile = {"kakao_id": kakao_id, "nickname": nickname}
        start = client.get("/api/auth/kakao/login", params={"next": next_url}, follow_redirects=False)
        state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
        back = client.get("/api/auth/kakao/callback", params={"code": "ok", "state": state}, follow_redirects=False)
        token = parse_qs(urlsplit(back.headers["location"]).fragment)["bb_token"][0]
        return {"Authorization": f"Bearer {token}"}

    return do
