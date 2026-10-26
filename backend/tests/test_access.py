"""권한·접근 제어 테스트."""

from fastapi.testclient import TestClient

from pgm.app import create_app

from .conftest import future, iso


def _reserve(client, item_id):
    r = client.post(
        "/reservations",
        json={"item_id": item_id, "start_at": iso(future(1)), "end_at": iso(future(2)), "purpose": "회의 발표"},
    )
    assert r.status_code == 201
    return r.json()["reservation"]["id"]


def test_requires_login():
    anon = TestClient(create_app(run_startup=False))
    for path in ("/items", "/dashboard", "/reservations/mine", "/admin/reservations", "/auth/me"):
        assert anon.get(path).status_code == 401, path


def test_wrong_password(users):
    c = TestClient(create_app(run_startup=False))
    r = c.post("/auth/login", json={"email": "alice@t.test", "password": "nope"})
    assert r.status_code == 401
    r = c.post("/auth/login", json={"email": "ghost@t.test", "password": "nope"})
    assert r.status_code == 401


def test_session_cookie_is_httponly(users):
    c = TestClient(create_app(run_startup=False))
    r = c.post("/auth/login", json={"email": "alice@t.test", "password": "password123"})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert "password" not in r.text.lower() or "password_hash" not in r.text


def test_user_cannot_see_or_change_others_reservations(clients, item):
    rid = _reserve(clients["alice"], item.id)
    bob = clients["bob"]
    assert bob.get(f"/reservations/{rid}").status_code == 404
    assert bob.post(f"/reservations/{rid}/cancel", json={}).status_code == 404
    assert bob.post(f"/reservations/{rid}/return-request", json={}).status_code == 404
    assert all(r["id"] != rid for r in bob.get("/reservations/mine").json()["reservations"])
    # 본인은 볼 수 있음
    assert clients["alice"].get(f"/reservations/{rid}").status_code == 200


def test_item_detail_hides_other_users_identity(clients, item):
    rid = _reserve(clients["alice"], item.id)
    clients["admin"].post(f"/admin/reservations/{rid}/approve")
    busy = clients["bob"].get(f"/items/{item.id}").json()["busy"]
    assert busy and "user_name" not in busy[0] and "reservation_id" not in busy[0]
    admin_busy = clients["admin"].get(f"/items/{item.id}").json()["busy"]
    assert admin_busy[0]["user_name"]


def test_user_cannot_use_admin_endpoints(clients, item):
    rid = _reserve(clients["alice"], item.id)
    alice = clients["alice"]
    calls = [
        ("get", "/admin/reservations", None),
        ("post", f"/admin/reservations/{rid}/approve", None),
        ("post", f"/admin/reservations/{rid}/reject", {"reason": "x"}),
        ("post", f"/admin/reservations/{rid}/checkout", None),
        ("post", f"/admin/reservations/{rid}/return", {"condition": "normal"}),
        ("get", "/admin/items", None),
        ("post", "/admin/items", {"asset_code": "X-1", "name": "x", "category": "x"}),
        ("put", f"/admin/items/{item.id}", {"asset_code": "X-1", "name": "x", "category": "x", "status": "repair"}),
        ("delete", f"/admin/items/{item.id}", None),
        ("get", "/admin/reports", None),
        ("patch", "/admin/reports/1", {"status": "resolved"}),
        ("get", "/admin/users", None),
        ("post", "/admin/users", {"email": "x@x.x", "name": "x", "password": "12345678", "role": "admin"}),
    ]
    for method, path, body in calls:
        kw = {"json": body} if body is not None else {}
        r = getattr(alice, method)(path, **kw)
        assert r.status_code == 403, (method, path, r.status_code)
    # 상태가 바뀌지 않았는지 확인
    assert alice.get(f"/reservations/{rid}").json()["reservation"]["status"] == "pending"


def test_users_cannot_list_retired_items(clients, db, item):
    from .conftest import make_item

    make_item(db, "OLD-001", "구형 멀티탭", status="retired")
    codes = [i["asset_code"] for i in clients["alice"].get("/items").json()["items"]]
    assert "OLD-001" not in codes
    assert clients["alice"].get("/items?status=retired").status_code == 403
    assert "OLD-001" in [i["asset_code"] for i in clients["admin"].get("/items?status=retired").json()["items"]]


def test_item_with_history_cannot_be_deleted(clients, item):
    _reserve(clients["alice"], item.id)
    r = clients["admin"].delete(f"/admin/items/{item.id}")
    assert r.status_code == 409 and "보관 종료" in r.json()["detail"]


def test_super_admin_role_cannot_be_changed_from_api(clients, users, db):
    # role 을 보내도 무시된다 (최고 관리자는 화면·API 로 만들거나 뺄 수 없음)
    clients["admin"].patch(f"/admin/users/{users['alice'].id}", json={"role": "admin"})
    assert clients["alice"].get("/admin/users").status_code == 403
    clients["admin"].patch(f"/admin/users/{users['admin2'].id}", json={"role": "user"})
    assert clients["admin2"].get("/admin/users").status_code == 200


def test_org_admin_rights_apply_immediately(clients, users, db):
    # 토큰에 권한을 담지 않으므로 기관 관리자 지정·해제가 바로 반영된다
    from .conftest import make_org

    org = make_org(db, "o-x", "엑스 기관", "other")
    assert clients["alice"].get("/admin/reservations").status_code == 403
    r = clients["admin"].post(f"/admin/orgs/{org.id}/admins", json={"email": users["alice"].email})
    assert r.status_code == 201
    assert clients["alice"].get("/admin/reservations").status_code == 200
    clients["admin"].delete(f"/admin/orgs/{org.id}/admins/{users['alice'].id}")
    assert clients["alice"].get("/admin/reservations").status_code == 403


def test_create_user_as_org_admin(clients, db):
    from .conftest import make_org

    org = make_org(db, "o-y", "와이 기관", "other")
    r = clients["admin"].post(
        "/admin/users", json={"email": "staff@t.test", "name": "담당", "password": "password123", "org_id": org.id}
    )
    assert r.status_code == 201 and r.json()["user"]["role"] == "user"
    rows = {u["email"]: u for u in clients["admin"].get("/admin/users").json()["users"]}
    assert [o["name"] for o in rows["staff@t.test"]["managed_orgs"]] == ["와이 기관"]


# ---------------------------------------------------------------- 관리자 비밀 코드


def _login(email, password="password123", code=None):
    from fastapi.testclient import TestClient

    c = TestClient(create_app(run_startup=False))
    body = {"email": email, "password": password}
    if code is not None:
        body["admin_code"] = code
    return c, c.post("/auth/login", json=body)


def test_admin_code_required_for_staff_only(users, db, monkeypatch):
    from pgm import config

    from .conftest import make_org, make_org_admin

    monkeypatch.setattr(config, "ADMIN_ACCESS_CODE", "Secret-2026")
    org = make_org(db, "o-z", "제트 기관", "other")
    make_org_admin(db, org, users["bob"])
    # 일반 회원은 코드 없이 로그인
    assert _login("alice@t.test")[1].status_code == 200
    # 최고 관리자·기관 관리자는 코드 필요
    for email in ("admin@t.test", "bob@t.test"):
        c, r = _login(email)
        assert r.status_code == 401 and r.json()["code"] == "admin_code_required"
        assert "set-cookie" not in r.headers and c.get("/auth/me").status_code == 401
        c, r = _login(email, code="Secret-2026")
        assert r.status_code == 200 and c.get("/auth/me").status_code == 200
    # 비밀번호가 틀리면 코드 여부를 알려 주지 않음
    assert _login("admin@t.test", password="wrong-pass")[1].status_code == 401
    assert "code" not in _login("admin@t.test", password="wrong-pass")[1].json()


def test_admin_code_lockout(users, db, monkeypatch):
    from pgm import config

    monkeypatch.setattr(config, "ADMIN_ACCESS_CODE", "Secret-2026")
    for i in range(config.ADMIN_CODE_MAX_FAILURES - 1):
        r = _login("admin@t.test", code="nope")[1]
        assert r.status_code == 401 and r.json()["code"] == "admin_code_invalid"
    r = _login("admin@t.test", code="nope")[1]
    assert r.status_code == 429 and r.json()["code"] == "admin_code_locked"
    # 잠긴 동안은 맞는 코드도 거절
    assert _login("admin@t.test", code="Secret-2026")[1].status_code == 429


def test_no_admin_code_configured_keeps_password_login(users, monkeypatch):
    from pgm import config

    monkeypatch.setattr(config, "ADMIN_ACCESS_CODE", "")
    assert _login("admin@t.test")[1].status_code == 200


def test_seed_refuses_in_production(monkeypatch):
    import pytest

    from pgm import config, seed
    from pgm.db import engine

    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    with pytest.raises(RuntimeError):
        seed.seed_demo(engine)


# ---------------------------------------------------------------- 계정 중지·삭제 (최고 관리자만)


def test_suspend_blocks_login_and_existing_session(clients, users):
    alice = clients["alice"]
    assert alice.get("/auth/me").status_code == 200
    uid = users["alice"].id
    assert clients["admin"].post(f"/admin/users/{uid}/suspend", json={"reason": ""}).status_code == 422
    r = clients["admin"].post(f"/admin/users/{uid}/suspend", json={"reason": "규칙 위반"})
    assert r.status_code == 200 and r.json()["user"]["suspended"] is True
    # 이미 로그인한 세션도 바로 막힘
    assert alice.get("/auth/me").status_code == 401
    r = _login("alice@t.test")[1]
    assert r.status_code == 403 and r.json()["code"] == "account_suspended" and "규칙 위반" in r.json()["detail"]
    # 비밀번호가 틀리면 중지 여부를 알려 주지 않음
    assert _login("alice@t.test", password="wrong-pass")[1].status_code == 401
    clients["admin"].post(f"/admin/users/{uid}/unsuspend")
    assert _login("alice@t.test")[1].status_code == 200


def test_only_super_admin_can_suspend_or_delete(clients, users, db):
    from .conftest import make_org, make_org_admin

    org = make_org(db, "o-m", "엠 기관", "other")
    make_org_admin(db, org, users["bob"])
    uid = users["alice"].id
    for c in (clients["bob"], clients["alice"]):
        assert c.post(f"/admin/users/{uid}/suspend", json={"reason": "x"}).status_code == 403
        assert c.delete(f"/admin/users/{uid}").status_code == 403
    # 최고 관리자 자신·다른 최고 관리자는 대상이 될 수 없음
    assert clients["admin"].post(f"/admin/users/{users['admin'].id}/suspend", json={"reason": "x"}).status_code == 409
    assert clients["admin"].delete(f"/admin/users/{users['admin2'].id}").status_code == 409


def test_delete_without_history_removes_account(clients, users):
    r = clients["admin"].delete(f"/admin/users/{users['bob'].id}")
    assert r.status_code == 200 and r.json()["mode"] == "deleted"
    emails = [u["email"] for u in clients["admin"].get("/admin/users").json()["users"]]
    assert "bob@t.test" not in emails
    assert _login("bob@t.test")[1].status_code == 401


def test_delete_with_history_anonymizes_and_cancels(clients, users, item, db):
    from datetime import timedelta

    from pgm.models import Reservation
    from pgm.timeutil import now_utc

    rid = _reserve(clients["alice"], item.id)
    r = clients["admin"].delete(f"/admin/users/{users['alice'].id}")
    assert r.status_code == 200 and r.json()["mode"] == "anonymized"
    db.expire_all()
    res = db.get(Reservation, rid)
    assert res.status == "cancelled" and "계정 삭제" in res.cancel_reason
    row = next(u for u in clients["admin"].get("/admin/users").json()["users"] if u["id"] == users["alice"].id)
    assert row["name"] == "삭제된 회원" and row["email"].endswith("@deleted.invalid")
    assert _login("alice@t.test")[1].status_code == 401
    # 같은 이메일로 다시 가입할 수 있음 (개인정보가 지워졌으므로)
    assert clients["admin"].post(
        "/admin/users", json={"email": "alice@t.test", "name": "새 앨리스", "password": "password123"}
    ).status_code == 201

    # 반납하지 않은 물품이 있으면 삭제 불가
    db.add(Reservation(item_id=item.id, user_id=users["bob"].id, start_at=now_utc() - timedelta(hours=3),
                       end_at=now_utc() - timedelta(hours=1), purpose="테스트", status="in_use"))
    db.commit()
    r = clients["admin"].delete(f"/admin/users/{users['bob'].id}")
    assert r.status_code == 409 and "반납" in r.json()["detail"]


def test_grant_and_revoke_super_needs_code(clients, users, monkeypatch):
    from pgm import config

    uid = users["alice"].id
    monkeypatch.setattr(config, "OWNER_EMAIL", "admin@t.test")
    # 소유자가 아닌 최고 관리자는 코드를 알아도 불가
    monkeypatch.setattr(config, "ADMIN_ACCESS_CODE", "Secret-2026")
    assert clients["admin2"].post(f"/admin/users/{uid}/grant-super", json={"admin_code": "Secret-2026"}).status_code == 403
    # 소유자 계정은 다른 관리자가 바꾸거나 해제할 수 없음
    assert clients["admin2"].patch(f"/admin/users/{users['admin'].id}", json={"password": "newpass123"}).status_code == 403
    assert clients["admin"].post(f"/admin/users/{users['admin'].id}/revoke-super", json={"admin_code": "Secret-2026"}).status_code == 409
    # 코드가 설정되지 않았으면 바꿀 수 없음
    monkeypatch.setattr(config, "ADMIN_ACCESS_CODE", "")
    assert clients["admin"].post(f"/admin/users/{uid}/grant-super", json={"admin_code": "x"}).status_code == 409
    monkeypatch.setattr(config, "ADMIN_ACCESS_CODE", "Secret-2026")
    assert clients["admin"].post(f"/admin/users/{uid}/grant-super", json={}).status_code == 401
    assert clients["admin"].post(f"/admin/users/{uid}/grant-super", json={"admin_code": "wrong"}).status_code == 401
    # 최고 관리자가 아니면 코드를 알아도 불가
    assert clients["bob"].post(f"/admin/users/{uid}/grant-super", json={"admin_code": "Secret-2026"}).status_code == 403
    r = clients["admin"].post(f"/admin/users/{uid}/grant-super", json={"admin_code": "Secret-2026"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "admin"
    assert clients["alice"].get("/admin/users").status_code == 200
    # 해제도 코드 필요, 자기 자신은 해제 불가
    assert clients["admin"].post(f"/admin/users/{users['admin'].id}/revoke-super", json={"admin_code": "Secret-2026"}).status_code == 409
    r = clients["admin"].post(f"/admin/users/{uid}/revoke-super", json={"admin_code": "Secret-2026"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "user"
    assert clients["alice"].get("/admin/users").status_code == 403


def test_item_list_is_paged(clients, db):
    from .conftest import make_item

    for n in range(45):
        make_item(db, f"P-{n:03d}", f"물품{n:03d}")
    r = clients["alice"].get("/items").json()
    assert len(r["items"]) == 40 and r["total"] == 45 and r["has_more"] is True
    r2 = clients["alice"].get("/items", params={"offset": 40}).json()
    assert len(r2["items"]) == 5 and r2["has_more"] is False
    r3 = clients["admin"].get("/admin/items", params={"limit": 10, "q": "물품00"}).json()
    assert r3["total"] == 10 and len(r3["items"]) == 10
    one = clients["admin"].get(f"/admin/items/{r3['items'][0]['id']}").json()["item"]
    assert one["id"] == r3["items"][0]["id"]
