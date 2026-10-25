import os

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/pgm_test"
)
os.environ.pop("BOOTSTRAP_ADMIN_EMAIL", None)

from datetime import timedelta  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlmodel import Session  # noqa: E402

from pgm.app import create_app  # noqa: E402
from pgm.db import engine, init_db  # noqa: E402
from pgm.models import Item, Organization, OrgAdmin, User  # noqa: E402
from sqlmodel import select  # noqa: E402
from pgm.security import hash_password  # noqa: E402
from pgm.timeutil import now_utc  # noqa: E402

PW = "password123"


@pytest.fixture(scope="session", autouse=True)
def _schema():
    init_db()
    yield


@pytest.fixture(autouse=True)
def clean_db():
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE pgm_damage_report, pgm_reservation, pgm_item, pgm_org_admin, pgm_email_token, "
                "pgm_user, pgm_sync_run, pgm_org RESTART IDENTITY CASCADE"
            )
        )
    from pgm import mailer

    mailer.OUTBOX.clear()
    yield


@pytest.fixture
def db():
    with Session(engine) as s:
        yield s


def make_user(db, email, role="user", name=None, verified=True):
    u = User(
        email=email,
        name=name or email.split("@")[0],
        role=role,
        password_hash=hash_password(PW),
        email_verified_at=now_utc() if verified else None,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def make_org(db, code="org-a", name="가온고등학교", kind="school", lat=37.55, lng=126.92):
    o = db.exec(select(Organization).where(Organization.code == code)).first()
    if o:
        return o
    o = Organization(kind=kind, code=code, name=name, lat=lat, lng=lng, geocode_status="manual")
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


def make_org_admin(db, org, user):
    db.add(OrgAdmin(org_id=org.id, user_id=user.id))
    db.commit()


def make_item(db, code="MIC-001", name="무선 마이크", status="normal", org=None, access="public"):
    org = org or make_org(db, "org-default", "기본 기관", "other")
    i = Item(org_id=org.id, access=access, asset_code=code, name=name, category="음향", status=status)
    db.add(i)
    db.commit()
    db.refresh(i)
    return i


@pytest.fixture
def users(db):
    return {
        "admin": make_user(db, "admin@t.test", "admin"),
        "admin2": make_user(db, "admin2@t.test", "admin"),
        "alice": make_user(db, "alice@t.test"),
        "bob": make_user(db, "bob@t.test"),
    }


@pytest.fixture
def item(db):
    return make_item(db)


def login(email):
    client = TestClient(create_app(run_startup=False))
    r = client.post("/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return client


@pytest.fixture
def clients(users):
    return {k: login(u.email) for k, u in users.items()}


def iso(dt):
    return dt.isoformat()


def future(hours: float):
    """현재 기준 hours 시간 뒤 (정각 기준으로 맞춤)"""
    base = now_utc().replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
    return base + timedelta(hours=hours)
