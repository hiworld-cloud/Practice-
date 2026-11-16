import httpx

from app import mailer


def test_without_key_only_logs(monkeypatch, caplog):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("보내면 안 돼요")))
    assert mailer.send_mail("me@example.com", "제목", "본문 링크", "<p>본문</p>") is False
    assert "본문 링크" in caplog.text  # 내 컴퓨터에서는 터미널에 찍힌 링크로 연습해요


def test_sends_with_resend(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, headers, json))
        return httpx.Response(200, json={"id": "abc"})

    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("MAIL_FROM", "BeautyBook <no-reply@example.com>")
    monkeypatch.setattr(httpx, "post", fake_post)
    assert mailer.send_mail("me@example.com", "제목", "본문", "<p>본문</p>") is True
    url, headers, body = calls[0]
    assert url == "https://api.resend.com/emails" and headers["Authorization"] == "Bearer re_test"
    assert body["to"] == ["me@example.com"] and body["from"] == "BeautyBook <no-reply@example.com>"


def test_resend_error_does_not_crash(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(403, text="only your own email"))
    assert mailer.send_mail("other@example.com", "제목", "본문", "<p>본문</p>") is False
