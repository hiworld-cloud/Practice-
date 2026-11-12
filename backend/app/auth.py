"""카카오 로그인 (OAuth 2.0) + 우리 서버의 로그인 토큰.

흐름 (화면은 GitHub Pages, 서버는 Render라고 할 때)
  1. 사용자가 "카카오 로그인" 버튼을 누르면 화면이 GET /api/auth/kakao/login?next=<돌아갈 주소> 로 이동해요.
  2. 서버는 카카오 로그인 페이지(kauth.kakao.com)로 보내요.
  3. 사용자가 카카오에서 로그인·동의하면, 카카오가 GET /api/auth/kakao/callback?code=... 로 돌려보내요.
  4. 서버는 code를 카카오에 보내 "카카오 토큰"을 받고, 그걸로 카카오 회원번호와 닉네임을 물어봐요.
  5. 처음 온 사람이면 User를 만들고, 우리 서버 전용 "로그인 토큰"을 만들어서
     <돌아갈 주소>#bb_token=... 으로 보내요. 화면은 이 토큰을 저장해 두고 요청할 때마다
     Authorization: Bearer <토큰> 헤더로 보내요.

필요한 환경변수 (Render의 Environment 화면, 또는 backend/.env)
  KAKAO_REST_API_KEY   카카오 앱의 REST API 키
  KAKAO_CLIENT_SECRET  카카오 앱의 Client Secret 코드 (켜 두었다면)
  KAKAO_REDIRECT_URI   카카오에 등록한 Redirect URI (기본: http://localhost:8000/api/auth/kakao/callback)
  SECRET_KEY           로그인 토큰 서명용 긴 무작위 문자열. 유출되면 아무나 토큰을 만들 수 있어요
  FRONTEND_URL         로그인 후 돌아갈 기본 화면 주소 (예: https://hiworld-cloud.github.io/Practice-/)
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional
from urllib.parse import urlencode, urlsplit

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from . import db
from .models import User

log = logging.getLogger("beautybook.auth")

KAKAO_AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USER_URL = "https://kapi.kakao.com/v2/user/me"

TOKEN_TTL = 60 * 60 * 24 * 7  # 로그인 유지 기간: 7일
STATE_TTL = 60 * 10  # 카카오 로그인 화면에 머물 수 있는 시간: 10분
STATE_COOKIE = "bb_kakao_state"

SessionDep = Annotated[Session, Depends(db.get_session)]
router = APIRouter(prefix="/api/auth", tags=["auth"])


ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
LOGIN_ENV_KEYS = ("KAKAO_REST_API_KEY", "KAKAO_CLIENT_SECRET", "KAKAO_REDIRECT_URI", "SECRET_KEY", "FRONTEND_URL")


def load_login_env(path: Path = ENV_FILE) -> None:
    """내 컴퓨터에서 연습할 때 backend/.env 의 카카오 설정만 읽어요.
    (DATABASE_URL 같은 다른 값은 읽지 않아요. 실수로 Supabase에 연결되지 않게)"""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = raw.strip().partition("=")
        if sep and key.strip() in LOGIN_ENV_KEYS:
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_login_env()


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


# SECRET_KEY가 없으면(내 컴퓨터에서 연습할 때) 서버를 켤 때마다 새로 만들어요.
# 이 경우 서버를 다시 켜면 다시 로그인해야 해요. 배포 서버에는 꼭 SECRET_KEY를 넣으세요.
_dev_secret = secrets.token_urlsafe(32)


def _secret() -> bytes:
    key = _env("SECRET_KEY")
    if not key:
        return _dev_secret.encode()
    return key.encode()


# ---------- 서명된 문자열 (로그인 토큰, state 쿠키에 사용) ----------

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign(payload: dict, purpose: str) -> str:
    """payload를 JSON으로 바꾸고 SECRET_KEY로 서명해요. 서명이 있어서 사용자가 내용을 고칠 수 없어요."""
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    mac = hmac.new(_secret(), f"{purpose}.{body}".encode(), hashlib.sha256).digest()
    return f"{body}.{_b64(mac)}"


def unsign(token: str, purpose: str) -> Optional[dict]:
    """서명이 맞고 기한(exp)이 지나지 않았으면 payload를, 아니면 None을 돌려줘요."""
    try:
        body, mac = token.split(".")
        expected = hmac.new(_secret(), f"{purpose}.{body}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_unb64(mac), expected):
            return None
        payload = json.loads(_unb64(body))
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get("exp", 0) < time.time():
        return None
    return payload


def make_login_token(user: User) -> str:
    return sign({"uid": user.id, "exp": int(time.time()) + TOKEN_TTL}, "login")


# ---------- "로그인한 사람" 확인 (다른 API에서 Depends로 사용) ----------

def _user_from_header(authorization: Optional[str], session: Session) -> Optional[User]:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    payload = unsign(authorization[7:].strip(), "login")
    if not payload:
        raise HTTPException(401, detail={"code": "invalid_token"})
    user = session.get(User, payload.get("uid"))
    if not user:
        raise HTTPException(401, detail={"code": "invalid_token"})
    return user


def optional_user(session: SessionDep, authorization: Annotated[Optional[str], Header()] = None) -> Optional[User]:
    """로그인했으면 User, 안 했으면 None. (토큰이 위조·만료됐으면 401)"""
    return _user_from_header(authorization, session)


def current_user(session: SessionDep, authorization: Annotated[Optional[str], Header()] = None) -> User:
    """로그인한 사람만 통과. 아니면 401 login_required."""
    user = _user_from_header(authorization, session)
    if not user:
        raise HTTPException(401, detail={"code": "login_required"})
    return user


OptionalUserDep = Annotated[Optional[User], Depends(optional_user)]
UserDep = Annotated[User, Depends(current_user)]


def user_out(u: User) -> dict:
    return {"id": u.id, "nickname": u.nickname}


# ---------- 로그인 후 돌아갈 주소 검사 ----------

def _origin(url: str) -> str:
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}".lower() if p.scheme in ("http", "https") and p.netloc else ""


def _frontend_url() -> str:
    return _env("FRONTEND_URL", "/")


def safe_next(next_url: Optional[str], request: Request) -> str:
    """아무 사이트로나 토큰을 보내면 안 되니까, 허락된 주소로만 돌려보내요.

    허락: FRONTEND_URL, CORS_ORIGINS에 적힌 주소, 이 서버 자신, 내 컴퓨터(localhost/127.0.0.1)
    """
    if not next_url:
        return _frontend_url()
    origin = _origin(next_url)
    if not origin:
        return _frontend_url()
    allowed = {_origin(_frontend_url()), _origin(str(request.base_url))}
    allowed |= {_origin(o.strip()) for o in _env("CORS_ORIGINS").split(",") if o.strip() != "*"}
    host = urlsplit(next_url).hostname or ""
    if origin in allowed or host in ("localhost", "127.0.0.1"):
        return next_url.split("#")[0]
    return _frontend_url()


def _back(next_url: str, **params: str) -> RedirectResponse:
    """돌아갈 주소 뒤에 #bb_token=... 처럼 붙여서 보내요. # 뒤는 서버로 전송되지 않아서 기록에 남지 않아요."""
    res = RedirectResponse(f"{next_url}#{urlencode(params)}", status_code=302)
    res.delete_cookie(STATE_COOKIE, path="/api/auth/kakao")
    return res


# ---------- 카카오와 대화하는 부분 (테스트에서는 가짜로 바꿔 끼워요) ----------

def kakao_redirect_uri() -> str:
    return _env("KAKAO_REDIRECT_URI", "http://localhost:8000/api/auth/kakao/callback")


def kakao_exchange_code(code: str) -> str:
    """카카오가 준 code를 카카오 access token으로 바꿔요."""
    data = {
        "grant_type": "authorization_code",
        "client_id": _env("KAKAO_REST_API_KEY"),
        "redirect_uri": kakao_redirect_uri(),
        "code": code,
    }
    if _env("KAKAO_CLIENT_SECRET"):
        data["client_secret"] = _env("KAKAO_CLIENT_SECRET")
    res = httpx.post(KAKAO_TOKEN_URL, data=data, timeout=10)
    if res.status_code != 200:
        # 예: KOE010(Client Secret 틀림), KOE006(Redirect URI 미등록). Render Logs에서 볼 수 있어요.
        log.warning("Kakao token error %s: %s", res.status_code, res.text[:300])
        raise ValueError("kakao_token_failed")
    return res.json()["access_token"]


def kakao_fetch_profile(access_token: str) -> dict:
    """카카오 회원번호와 닉네임을 받아요."""
    res = httpx.get(KAKAO_USER_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    if res.status_code != 200:
        log.warning("Kakao profile error %s: %s", res.status_code, res.text[:300])
        raise ValueError("kakao_profile_failed")
    data = res.json()
    profile = (data.get("kakao_account") or {}).get("profile") or {}
    nickname = profile.get("nickname") or (data.get("properties") or {}).get("nickname") or ""
    return {"kakao_id": int(data["id"]), "nickname": nickname}


# ---------- API ----------

@router.get("/kakao/login")
def kakao_login(request: Request, next: Optional[str] = Query(default=None)):
    """카카오 로그인 화면으로 보내요. 화면에서는 이 주소로 이동(location.href)만 하면 돼요."""
    client_id = _env("KAKAO_REST_API_KEY")
    if not client_id:  # 서버에 카카오 키를 아직 안 넣었을 때
        return _back(safe_next(next, request), login_error="kakao_not_configured")
    nonce = secrets.token_urlsafe(16)
    params = {
        "client_id": client_id,
        "redirect_uri": kakao_redirect_uri(),
        "response_type": "code",
        "state": nonce,
    }
    res = RedirectResponse(f"{KAKAO_AUTHORIZE_URL}?{urlencode(params)}", status_code=302)
    # state: 로그인을 시작한 브라우저와 돌아온 브라우저가 같은지 확인하는 일회용 번호 (CSRF 방지)
    cookie = sign({"nonce": nonce, "next": safe_next(next, request), "exp": int(time.time()) + STATE_TTL}, "state")
    res.set_cookie(STATE_COOKIE, cookie, max_age=STATE_TTL, httponly=True, samesite="lax",
                   secure=kakao_redirect_uri().startswith("https://"), path="/api/auth/kakao")
    return res


@router.get("/kakao/callback")
def kakao_callback(request: Request, session: SessionDep, code: Optional[str] = None,
                   state: Optional[str] = None, error: Optional[str] = None):
    saved = unsign(request.cookies.get(STATE_COOKIE, ""), "state")
    if not saved or not state or not hmac.compare_digest(saved["nonce"], state):
        # 10분이 지났거나, 다른 브라우저에서 돌아왔거나, 누가 주소를 꾸며 낸 경우
        return _back(_frontend_url(), login_error="invalid_state")
    next_url = saved["next"]
    if error or not code:  # 사용자가 카카오 화면에서 "취소"를 누른 경우 등
        return _back(next_url, login_error=error or "no_code")

    try:
        profile = kakao_fetch_profile(kakao_exchange_code(code))
    except (ValueError, KeyError, httpx.HTTPError) as e:
        log.warning("Kakao login failed: %r", e)
        return _back(next_url, login_error="kakao_failed")

    user = session.exec(select(User).where(User.kakao_id == profile["kakao_id"])).first()
    now = datetime.now(timezone.utc)
    if not user:
        user = User(kakao_id=profile["kakao_id"], nickname=profile["nickname"] or "카카오회원")
    elif profile["nickname"]:
        user.nickname = profile["nickname"]
    user.last_login_at = now
    session.add(user)
    session.commit()
    session.refresh(user)
    return _back(next_url, bb_token=make_login_token(user))


@router.get("/me")
def me(user: UserDep):
    """지금 로그인한 사람. 로그인 안 했으면 401."""
    return user_out(user)
