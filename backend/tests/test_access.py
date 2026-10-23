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


def test_admin_cannot_demote_self(clients, users):
    r = clients["admin"].patch(f"/admin/users/{users['admin'].id}", json={"role": "user"})
    assert r.status_code == 409


def test_role_change_applies_immediately(clients, users):
    # 토큰에 역할을 담지 않으므로 관리자 해제가 즉시 반영된다
    assert clients["admin2"].get("/admin/users").status_code == 200
    clients["admin"].patch(f"/admin/users/{users['admin2'].id}", json={"role": "user"})
    assert clients["admin2"].get("/admin/users").status_code == 403


def test_seed_refuses_in_production(monkeypatch):
    import pytest

    from pgm import config, seed
    from pgm.db import engine

    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    with pytest.raises(RuntimeError):
        seed.seed_demo(engine)
