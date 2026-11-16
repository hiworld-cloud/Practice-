"""이메일 + 비밀번호로 회원가입 / 로그인.

로그인에 성공하면 카카오 로그인과 똑같은 "로그인 토큰"을 줘요 (auth.py의 make_login_token).
그래서 리뷰 쓰기 같은 다른 API는 어떤 방법으로 로그인했는지 신경 쓰지 않아요.

비밀번호를 지키는 방법
  - 비밀번호 원문은 어디에도 저장하지 않아요. scrypt로 "되돌릴 수 없게 바꾼 값"(해시)만 저장해요.
    로그인할 때는 입력한 비밀번호를 똑같이 바꿔서 저장된 값과 같은지 비교해요.
  - 사람마다 다른 무작위 값(salt)을 섞어서, 같은 비밀번호라도 저장된 값이 달라요.
  - 같은 이메일로 15분 안에 5번 틀리면 15분 동안 막아요 (비밀번호 맞히기 공격 방지).

아직 없는 것 (메일 발송 서비스가 필요해요)
  - 이메일 인증 (진짜 그 사람 이메일인지 확인)
  - 비밀번호 찾기
"""
import hashlib
import hmac
import re
import secrets
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from .auth import SessionDep, make_login_token, user_out
from .models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

PASSWORD_MIN = 8
MAX_FAILS = 5
LOCK_SECONDS = 15 * 60
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------- 비밀번호 해시 ----------

_SCRYPT = {"n": 2**14, "r": 8, "p": 1}  # 계산을 일부러 느리게 해서 대량으로 맞혀 보기 어렵게 해요


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **_SCRYPT)
    return f"scrypt${_SCRYPT['n']}${_SCRYPT['r']}${_SCRYPT['p']}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt":
            return False
        test = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), dklen=32, n=int(n), r=int(r), p=int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(test.hex(), digest)


# 없는 이메일로 로그인할 때도 비슷한 시간이 걸리게 해서, 응답 속도로 가입 여부를 알 수 없게 해요.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


# ---------- 틀린 횟수 세기 (서버 메모리에 저장, 서버가 다시 켜지면 초기화) ----------

_fails: dict[str, list[float]] = {}


def _recent_fails(email: str) -> list[float]:
    now = time.time()
    recent = [t for t in _fails.get(email, []) if now - t < LOCK_SECONDS]
    _fails[email] = recent
    return recent


def reset_fails() -> None:
    _fails.clear()


# ---------- 요청 형태 ----------

class SignupIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)
    nickname: str = Field(max_length=20)


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


def _clean_email(email: str) -> str:
    return email.strip().lower()


def _login_result(user: User) -> dict:
    return {"token": make_login_token(user), "user": user_out(user)}


# ---------- API ----------

@router.post("/signup", status_code=201)
def signup(body: SignupIn, session: SessionDep):
    email = _clean_email(body.email)
    nickname = body.nickname.strip()
    if not EMAIL_RE.match(email):
        raise HTTPException(422, detail={"code": "invalid_email"})
    if len(body.password) < PASSWORD_MIN or body.password.isdigit() or body.password.isalpha():
        # 8자 이상 + 숫자만/글자만은 안 됨
        raise HTTPException(422, detail={"code": "weak_password"})
    if not nickname:
        raise HTTPException(422, detail={"code": "nickname_required"})
    if session.exec(select(User.id).where(User.email == email)).first():
        raise HTTPException(409, detail={"code": "email_taken"})

    user = User(email=email, password_hash=hash_password(body.password), nickname=nickname)
    session.add(user)
    try:
        session.commit()
    except IntegrityError:  # 거의 동시에 같은 이메일로 두 번 가입한 경우
        session.rollback()
        raise HTTPException(409, detail={"code": "email_taken"})
    session.refresh(user)
    return _login_result(user)


@router.post("/login")
def login(body: LoginIn, session: SessionDep):
    email = _clean_email(body.email)
    if len(_recent_fails(email)) >= MAX_FAILS:
        raise HTTPException(429, detail={"code": "too_many_attempts"})

    user = session.exec(select(User).where(User.email == email)).first()
    ok = verify_password(body.password, user.password_hash if user and user.password_hash else _DUMMY_HASH)
    if not user or not user.password_hash or not ok:
        _fails[email].append(time.time())
        # 이메일이 틀렸는지 비밀번호가 틀렸는지 알려 주지 않아요 (가입 여부를 알 수 없게)
        raise HTTPException(401, detail={"code": "wrong_credentials"})

    _fails.pop(email, None)
    user.last_login_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()
    session.refresh(user)
    return _login_result(user)
