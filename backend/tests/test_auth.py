"""이메일 인증, 비밀번호 재설정, 학생 연령 확인 테스트."""

import urllib.parse
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from pgm import config, mailer
from pgm.app import create_app
from pgm.models import EmailToken

from .conftest import make_org


def anon():
    return TestClient(create_app(run_startup=False))


def token_of(link: str) -> str:
    return urllib.parse.parse_qs(urllib.parse.urlparse(link).query)["token"][0]


def years_ago(n: int, days: int = 0) -> str:
    t = date.today()
    return (date(t.year - n, t.month, min(t.day, 28)) - timedelta(days=days)).isoformat()


BODY = {"email": "new@t.test", "name": "새 회원", "password": "password123"}


def test_signup_requires_email_verification_before_login(db):
    c = anon()
    r = c.post("/auth/signup", json=BODY)
    assert r.status_code == 201
    assert "set-cookie" not in r.headers  # 가입만으로는 로그인되지 않음
    assert r.json()["mail"] == "not_sent_dev"  # 키가 없는 개발 환경: 보냈다고 하지 않음
    assert len(mailer.OUTBOX) == 1 and mailer.OUTBOX[0].to == "new@t.test"
    assert r.json()["dev_link"] in mailer.OUTBOX[0].text

    # 인증 전 로그인 → 403 + 안내 코드 (비밀번호가 틀리면 401 로 같은 응답)
    r = c.post("/auth/login", json={"email": "new@t.test", "password": "password123"})
    assert r.status_code == 403 and r.json()["code"] == "email_not_verified"
    assert c.post("/auth/login", json={"email": "new@t.test", "password": "wrong-pass"}).status_code == 401
    assert c.get("/auth/me").status_code == 401

    # 링크로 인증하면 바로 로그인
    token = token_of(mailer.OUTBOX[0].text.split("이메일 인증하기: ")[1].split()[0])
    r = c.post("/auth/verify-email", json={"token": token})
    assert r.status_code == 200 and "set-cookie" in r.headers
    assert c.get("/auth/me").json()["user"]["email"] == "new@t.test"
    # 같은 링크는 다시 쓸 수 없음
    assert anon().post("/auth/verify-email", json={"token": token}).status_code == 400
    # 이후 일반 로그인 가능
    assert anon().post("/auth/login", json={"email": "new@t.test", "password": "password123"}).status_code == 200


def test_tokens_are_hashed_and_expire(db):
    c = anon()
    link = c.post("/auth/signup", json=BODY).json()["dev_link"]
    raw = token_of(link)
    tok = db.exec(select(EmailToken)).one()
    assert tok.token_hash != raw and len(tok.token_hash) == 64  # 원문은 저장하지 않음
    tok.expires_at = tok.created_at - timedelta(seconds=1)
    db.commit()
    r = c.post("/auth/verify-email", json={"token": raw})
    assert r.status_code == 400 and "기간" in r.json()["detail"]
    assert c.post("/auth/verify-email", json={"token": "x" * 40}).status_code == 400


def test_resend_is_generic_and_rate_limited(db):
    c = anon()
    first = c.post("/auth/signup", json=BODY).json()["dev_link"]
    # 방금 보냈으므로 재발송 제한
    assert c.post("/auth/resend-verification", json={"email": "new@t.test"}).status_code == 429
    # 없는 계정도 같은 응답 (가입 여부 노출 방지)
    r = c.post("/auth/resend-verification", json={"email": "nobody@t.test"})
    assert r.status_code == 200 and "dev_link" not in r.json()
    # 제한 시간이 지나면 다시 보내고, 이전 링크는 무효
    for t in db.exec(select(EmailToken)).all():
        t.created_at = t.created_at - timedelta(minutes=5)
    db.commit()
    second = c.post("/auth/resend-verification", json={"email": "new@t.test"}).json()["dev_link"]
    assert c.post("/auth/verify-email", json={"token": token_of(first)}).status_code == 400
    assert c.post("/auth/verify-email", json={"token": token_of(second)}).status_code == 200


def test_production_without_mail_key_reports_failure(db, monkeypatch):
    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    monkeypatch.setattr(config, "SMTP_USER", "")
    monkeypatch.setattr(config, "RESEND_API_KEY", "")
    r = anon().post("/auth/signup", json=BODY)
    assert r.status_code == 201
    body = r.json()
    assert body["mail"] == "failed" and "SMTP" in body["message"] and "dev_link" not in body
    assert mailer.OUTBOX == []


class FakeSMTP:
    sent: list = []
    fail_login = False

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, user, pw):
        import smtplib

        if FakeSMTP.fail_login:
            raise smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")
        self.user, self.pw = user, pw

    def send_message(self, msg):
        FakeSMTP.sent.append((self.host, self.port, self.user, self.pw, msg))


def test_gmail_smtp_sends_real_mail(db, monkeypatch):
    import smtplib

    FakeSMTP.sent, FakeSMTP.fail_login = [], False
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(config, "SMTP_USER", "school.goods@gmail.com")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "abcdefghijklmnop")
    monkeypatch.setattr(config, "MAIL_FROM", "")
    r = anon().post("/auth/signup", json=BODY)
    assert r.json()["mail"] == "sent" and "dev_link" not in r.json()  # 실제 발송 시 링크를 화면에 주지 않음
    host, port, user, pw, msg = FakeSMTP.sent[0]
    assert (host, port, user, pw) == ("smtp.gmail.com", 465, "school.goods@gmail.com", "abcdefghijklmnop")
    assert msg["To"] == "new@t.test" and "school.goods@gmail.com" in msg["From"]
    assert "/verify-email?token=" in msg.get_body(("plain",)).get_content()
    assert mailer.OUTBOX == []


def test_gmail_wrong_app_password_is_reported(db, monkeypatch):
    import smtplib

    FakeSMTP.sent, FakeSMTP.fail_login = [], True
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(config, "SMTP_USER", "school.goods@gmail.com")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "wrong")
    r = anon().post("/auth/signup", json=BODY)
    assert r.json()["mail"] == "failed" and "앱 비밀번호" in r.json()["message"]
    FakeSMTP.fail_login = False


def test_password_reset(db, users):
    c = anon()
    r = c.post("/auth/password-reset/request", json={"email": "alice@t.test"})
    link = r.json()["dev_link"]
    assert "/reset-password?token=" in link
    assert anon().post("/auth/password-reset/request", json={"email": "ghost@t.test"}).json().get("dev_link") is None
    assert c.post("/auth/password-reset/confirm", json={"token": token_of(link), "password": "short"}).status_code == 422
    assert c.post("/auth/password-reset/confirm", json={"token": token_of(link), "password": "brandnew123"}).status_code == 200
    assert c.post("/auth/password-reset/confirm", json={"token": token_of(link), "password": "again12345"}).status_code == 400
    assert anon().post("/auth/login", json={"email": "alice@t.test", "password": "brandnew123"}).status_code == 200
    assert anon().post("/auth/login", json={"email": "alice@t.test", "password": "password123"}).status_code == 401


def test_admin_can_mark_verified(db, clients):
    anon().post("/auth/signup", json=BODY)
    uid = next(u["id"] for u in clients["admin"].get("/admin/users").json()["users"] if u["email"] == "new@t.test")
    assert clients["admin"].patch(f"/admin/users/{uid}", json={"verify_email": True}).status_code == 200
    assert anon().post("/auth/login", json={"email": "new@t.test", "password": "password123"}).status_code == 200


# ---------------------------------------------------------------- 학생 연령 확인


@pytest.fixture
def high(db):
    o = make_org(db, "s-high", "가온고등학교", "school")
    o.subtype = "고등학교"
    db.commit()
    return o


@pytest.fixture
def middle(db):
    o = make_org(db, "s-mid", "한빛중학교", "school")
    o.subtype = "중학교"
    db.commit()
    return o


def student(school_id, birth, email="s@t.test"):
    body = {**BODY, "email": email, "is_student": True, "school_id": school_id, "student_no": "10101"}
    if birth is not None:
        body["birth_date"] = birth
    return anon().post("/auth/signup", json=body)


def test_student_needs_birth_date(high):
    r = student(high.id, None)
    assert r.status_code == 422 and "생년월일" in r.json()["detail"]


def test_under_14_cannot_sign_up(high, middle):
    r = student(middle.id, years_ago(13))
    assert r.status_code == 422 and "14세 미만" in r.json()["detail"]
    # 생일이 내일이면 아직 만 13세
    t = date.today()
    tomorrow_14 = (date(t.year - 14, t.month, min(t.day, 28)) + timedelta(days=1)).isoformat()
    assert student(middle.id, tomorrow_14).status_code == 422
    assert student(middle.id, years_ago(14, days=1), "ok@t.test").status_code == 201


def test_age_must_fit_school_level(high, middle):
    r = student(high.id, years_ago(30))
    assert r.status_code == 422 and "고등학교" in r.json()["detail"]
    assert student(high.id, years_ago(17)).status_code == 201
    assert student(middle.id, years_ago(25), "m@t.test").status_code == 422
    future = (date.today() + timedelta(days=3)).isoformat()
    assert student(high.id, future, "f@t.test").status_code == 422


def test_birth_date_shown_to_school_admin(db, high, users):
    from .conftest import login, make_org_admin

    make_org_admin(db, high, users["bob"])
    student(high.id, years_ago(16))
    rows = login(users["bob"].email).get("/admin/students").json()["students"]
    assert rows[0]["age"] == 16 and rows[0]["birth_date"]
