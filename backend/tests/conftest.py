import os
import tempfile

import pytest

# 테스트는 실제 DB 파일을 건드리지 않도록 임시 SQLite 파일을 씁니다 (app import 전에 설정).
_tmpdir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdir}/test.db"

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
