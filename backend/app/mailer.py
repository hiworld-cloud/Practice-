"""메일 보내기 (Resend 사용).

Resend(https://resend.com)는 무료로 하루 100통, 한 달 3,000통까지 보낼 수 있는 메일 발송 서비스예요.
우리 서버가 Resend에 "이 주소로 이 내용을 보내 줘"라고 요청하면 Resend가 대신 보내 줘요.

필요한 환경변수 (Render의 Environment 화면, 또는 backend/.env)
  RESEND_API_KEY  Resend > API Keys 에서 만든 키 (re_ 로 시작). 유출되면 남이 우리 이름으로 메일을 보낼 수 있어요
  MAIL_FROM       보내는 사람. 기본값은 "BeautyBook <onboarding@resend.dev>"
                  ※ 도메인을 연결하기 전(onboarding@resend.dev)에는 Resend에 가입한 "내 이메일"로만 보낼 수 있어요.
                    .com 도메인을 사서 Resend에 등록하면 "BeautyBook <no-reply@내도메인.com>" 으로 바꿔서
                    누구에게나 보낼 수 있어요.

RESEND_API_KEY가 없으면(내 컴퓨터에서 연습할 때) 메일을 보내지 않고 서버 로그(터미널)에 내용을 찍어요.
터미널에 나온 링크를 복사해서 브라우저에 붙여 넣으면 메일을 받은 것과 똑같이 해 볼 수 있어요.
"""
import logging
import os

import httpx

log = logging.getLogger("beautybook.mail")
logging.basicConfig(level=logging.INFO)

RESEND_URL = "https://api.resend.com/emails"
DEFAULT_FROM = "BeautyBook <onboarding@resend.dev>"


def send_mail(to: str, subject: str, text: str, html: str) -> bool:
    """메일 한 통을 보내요. 성공하면 True. 실패해도 예외를 던지지 않고 로그만 남겨요."""
    key = (os.getenv("RESEND_API_KEY") or "").strip()
    if not key:
        log.info("[메일 미발송: RESEND_API_KEY 없음] to=%s subject=%s\n%s", to, subject, text)
        return False
    sender = (os.getenv("MAIL_FROM") or DEFAULT_FROM).strip()
    try:
        res = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={"from": sender, "to": [to], "subject": subject, "text": text, "html": html},
            timeout=10,
        )
    except httpx.HTTPError as e:
        log.warning("메일 발송 실패 (연결 오류) to=%s: %r", to, e)
        return False
    if res.status_code >= 300:
        # 예: 403 "You can only send testing emails to your own email address" → 도메인을 아직 등록 안 함
        log.warning("메일 발송 실패 %s to=%s: %s", res.status_code, to, res.text[:300])
        return False
    return True
