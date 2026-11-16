"""이메일 + 비밀번호로 회원가입 / 로그인.

로그인에 성공하면 카카오 로그인과 똑같은 "로그인 토큰"을 줘요 (auth.py의 make_login_token).
그래서 리뷰 쓰기 같은 다른 API는 어떤 방법으로 로그인했는지 신경 쓰지 않아요.

비밀번호를 지키는 방법
  - 비밀번호 원문은 어디에도 저장하지 않아요. scrypt로 "되돌릴 수 없게 바꾼 값"(해시)만 저장해요.
    로그인할 때는 입력한 비밀번호를 똑같이 바꿔서 저장된 값과 같은지 비교해요.
  - 사람마다 다른 무작위 값(salt)을 섞어서, 같은 비밀번호라도 저장된 값이 달라요.
  - 같은 이메일로 15분 안에 5번 틀리면 15분 동안 막아요 (비밀번호 맞히기 공격 방지).

이메일 인증 (진짜 그 사람 이메일인지 확인)
  1. 가입하면 바로 로그인시키지 않고, 인증 링크가 담긴 메일을 보내요 (mailer.py, 24시간 유효).
  2. 링크는 사이트 화면(FRONTEND_URL#verify_token=...)으로 가고, 화면이 POST /api/auth/verify-email 로
     토큰을 보내면 인증 완료 + 로그인이 돼요.
  3. 인증하기 전에는 로그인하면 403 email_not_verified 가 나와요. 화면에서 "인증 메일 다시 보내기"를 할 수 있어요.

비밀번호 찾기 (원래 비밀번호는 우리도 몰라요. 해시만 있으니까요. 그래서 "새로 정하는 링크"를 보내요)
  1. POST /api/auth/password-reset/request 에 이메일을 보내면, 가입된 이메일일 때만 재설정 링크를 메일로 보내요.
     가입 여부를 알 수 없게, 가입 안 된 이메일이어도 똑같이 "보냈어요"라고 답해요.
  2. 링크(FRONTEND_URL#reset_token=...)를 누르면 화면에서 새 비밀번호를 입력하고
     POST /api/auth/password-reset/confirm 으로 보내요.
  3. 링크는 30분만 유효하고, 한 번 비밀번호를 바꾸면 그 링크는 다시 못 써요
     (토큰 안에 "지금 비밀번호 해시의 지문"을 넣어 두어서, 비밀번호가 바뀌면 지문이 안 맞아요).
"""
import hashlib
import hmac
import re
import secrets
import time
from datetime import datetime, timezone

from html import escape
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from . import mailer
from .auth import SessionDep, _env, make_login_token, sign, unsign, user_out
from .models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

PASSWORD_MIN = 8
MAX_FAILS = 5
LOCK_SECONDS = 15 * 60
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VERIFY_TTL = 24 * 60 * 60  # 인증 링크 유효 시간: 24시간
RESET_TTL = 30 * 60  # 비밀번호 재설정 링크 유효 시간: 30분
MAIL_COOLDOWN = 60  # 같은 이메일로 메일을 다시 보내려면 1분 기다려야 해요 (메일 폭탄 방지)


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
    _mail_sent.clear()


# ---------- 메일 너무 자주 보내지 않기 (서버 메모리에 저장) ----------

_mail_sent: dict[tuple[str, str], float] = {}


def _cooldown_ok(kind: str, email: str) -> bool:
    """1분 안에 같은 종류의 메일을 이미 보냈으면 False."""
    now = time.time()
    if now - _mail_sent.get((kind, email), 0) < MAIL_COOLDOWN:
        return False
    _mail_sent[(kind, email)] = now
    return True


# ---------- 메일 속 링크 ----------

def _site_url(request: Request) -> str:
    """메일 속 링크가 열 화면 주소. 배포 서버는 FRONTEND_URL, 내 컴퓨터에서는 이 서버 주소."""
    url = _env("FRONTEND_URL")
    return url if url.startswith(("http://", "https://")) else str(request.base_url)


def _pw_fingerprint(password_hash: str) -> str:
    """비밀번호 해시의 짧은 지문. 비밀번호가 바뀌면 지문도 바뀌어서 예전 재설정 링크가 못 쓰게 돼요."""
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def make_verify_token(user: User) -> str:
    return sign({"uid": user.id, "email": user.email, "exp": int(time.time()) + VERIFY_TTL}, "verify")


def make_reset_token(user: User) -> str:
    return sign({"uid": user.id, "pw": _pw_fingerprint(user.password_hash or ""),
                 "exp": int(time.time()) + RESET_TTL}, "reset")


def _mail_html(nickname: str, intro: str, button: str, link: str, outro: str) -> str:
    return f"""<div style="font-family:sans-serif;max-width:480px;margin:auto;padding:24px;color:#222">
  <h2 style="margin:0 0 16px">BeautyBook</h2>
  <p>{escape(nickname)}님, 안녕하세요.</p>
  <p>{intro}</p>
  <p style="margin:28px 0"><a href="{escape(link)}" style="background:#d6336c;color:#fff;padding:12px 20px;
     border-radius:8px;text-decoration:none;font-weight:bold">{button}</a></p>
  <p style="color:#666;font-size:13px">{outro}<br>버튼이 안 눌리면 아래 주소를 복사해서 브라우저에 붙여 넣으세요.<br>
     <span style="word-break:break-all">{escape(link)}</span></p>
</div>"""


def send_verify_mail(user: User, site_url: str) -> None:
    link = f"{site_url}#verify_token={make_verify_token(user)}"
    mailer.send_mail(
        user.email, "[BeautyBook] 이메일 인증을 완료해 주세요",
        f"{user.nickname}님, BeautyBook 가입을 환영해요.\n아래 링크를 눌러 이메일 인증을 마쳐 주세요 (24시간 동안 유효해요).\n\n{link}\n\n"
        "직접 가입하지 않으셨다면 이 메일은 무시하셔도 돼요.",
        _mail_html(user.nickname, "BeautyBook 가입을 환영해요. 아래 버튼을 눌러 이메일 인증을 마쳐 주세요.",
                   "이메일 인증하기", link, "링크는 24시간 동안 유효해요. 직접 가입하지 않으셨다면 무시하셔도 돼요."),
    )


def send_reset_mail(user: User, site_url: str) -> None:
    link = f"{site_url}#reset_token={make_reset_token(user)}"
    mailer.send_mail(
        user.email, "[BeautyBook] 비밀번호 재설정 안내",
        f"{user.nickname}님, 비밀번호 재설정을 요청하셨어요.\n아래 링크에서 새 비밀번호를 정해 주세요 (30분 동안 유효해요).\n\n{link}\n\n"
        "요청하지 않으셨다면 이 메일은 무시하세요. 비밀번호는 바뀌지 않아요.",
        _mail_html(user.nickname, "비밀번호 재설정을 요청하셨어요. 아래 버튼을 눌러 새 비밀번호를 정해 주세요.",
                   "새 비밀번호 정하기", link, "링크는 30분 동안 한 번만 쓸 수 있어요. 요청하지 않으셨다면 무시하세요. 비밀번호는 바뀌지 않아요."),
    )


# ---------- 요청 형태 ----------

class SignupIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)
    nickname: str = Field(max_length=20)


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class EmailIn(BaseModel):
    email: str = Field(max_length=254)


class TokenIn(BaseModel):
    token: str = Field(max_length=1000)


class ResetIn(BaseModel):
    token: str = Field(max_length=1000)
    password: str = Field(max_length=128)


def _clean_email(email: str) -> str:
    return email.strip().lower()


def _login_result(user: User) -> dict:
    return {"token": make_login_token(user), "user": user_out(user)}


def _check_password_rule(password: str) -> None:
    if len(password) < PASSWORD_MIN or password.isdigit() or password.isalpha():
        # 8자 이상 + 숫자만/글자만은 안 됨
        raise HTTPException(422, detail={"code": "weak_password"})


def _find_email_user(session, email: str) -> Optional[User]:
    user = session.exec(select(User).where(User.email == email)).first()
    return user if user and user.password_hash else None


# ---------- API ----------

@router.post("/signup", status_code=201)
def signup(body: SignupIn, session: SessionDep, request: Request, tasks: BackgroundTasks):
    """가입만 하고 로그인은 아직이에요. 메일의 인증 링크를 눌러야 로그인할 수 있어요."""
    email = _clean_email(body.email)
    nickname = body.nickname.strip()
    if not EMAIL_RE.match(email):
        raise HTTPException(422, detail={"code": "invalid_email"})
    _check_password_rule(body.password)
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
    _cooldown_ok("verify", email)
    # 메일 보내기는 응답을 먼저 돌려준 뒤에 해요 (Resend가 느려도 화면이 기다리지 않게)
    tasks.add_task(send_verify_mail, user, _site_url(request))
    return {"verify_sent": True, "email": email}


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
    if not user.email_verified:
        # 비밀번호는 맞았지만 아직 메일 인증을 안 했어요
        raise HTTPException(403, detail={"code": "email_not_verified"})
    user.last_login_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()
    session.refresh(user)
    return _login_result(user)


@router.post("/verify-email")
def verify_email(body: TokenIn, session: SessionDep):
    """메일 속 인증 링크를 누르면 화면이 이 API를 불러요. 인증 완료 + 바로 로그인."""
    payload = unsign(body.token, "verify")
    user = session.get(User, payload.get("uid")) if payload else None
    if not user or user.email != payload.get("email"):
        # 24시간이 지났거나, 주소가 잘렸거나, 꾸며 낸 링크
        raise HTTPException(400, detail={"code": "invalid_link"})
    if user.email_verified:
        # 이미 인증한 링크를 또 누른 경우. 링크만으로 계속 로그인되면 안 되니까 토큰은 주지 않아요.
        return {"already": True}
    user.email_verified = True
    user.last_login_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()
    session.refresh(user)
    return _login_result(user)


@router.post("/verify-email/resend")
def resend_verify_email(body: EmailIn, session: SessionDep, request: Request, tasks: BackgroundTasks):
    """인증 메일 다시 보내기. 가입 여부를 알 수 없게 항상 같은 답을 해요."""
    email = _clean_email(body.email)
    user = _find_email_user(session, email)
    if user and not user.email_verified and _cooldown_ok("verify", email):
        tasks.add_task(send_verify_mail, user, _site_url(request))
    return {"ok": True}


@router.post("/password-reset/request")
def request_password_reset(body: EmailIn, session: SessionDep, request: Request, tasks: BackgroundTasks):
    """비밀번호 재설정 링크 보내기. 가입 여부를 알 수 없게 항상 같은 답을 해요."""
    email = _clean_email(body.email)
    user = _find_email_user(session, email)
    if user and _cooldown_ok("reset", email):
        tasks.add_task(send_reset_mail, user, _site_url(request))
    return {"ok": True}


@router.post("/password-reset/confirm")
def confirm_password_reset(body: ResetIn, session: SessionDep):
    """재설정 링크로 새 비밀번호 정하기. 성공하면 바로 로그인."""
    payload = unsign(body.token, "reset")
    user = session.get(User, payload.get("uid")) if payload else None
    if not user or not user.password_hash or not hmac.compare_digest(
            payload.get("pw", ""), _pw_fingerprint(user.password_hash)):
        # 30분이 지났거나, 이미 한 번 쓴 링크거나, 꾸며 낸 링크
        raise HTTPException(400, detail={"code": "invalid_link"})
    _check_password_rule(body.password)
    user.password_hash = hash_password(body.password)
    user.email_verified = True  # 메일을 받아서 링크를 눌렀으니 이메일 주인이 맞아요
    user.last_login_at = datetime.now(timezone.utc)
    _fails.pop(user.email, None)  # 틀린 횟수 때문에 막혀 있었다면 풀어 줘요
    session.add(user)
    session.commit()
    session.refresh(user)
    return _login_result(user)
