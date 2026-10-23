"""완료 기준 흐름: 검색 → 예약 → 승인 → 인계 → 반납 요청 → 반납 완료 → 재시작 후 유지."""

from datetime import timedelta

from fastapi.testclient import TestClient

from pgm.app import create_app
from pgm.timeutil import now_utc

from .conftest import PW, iso, make_item


def test_full_rental_flow_persists(clients, db, users):
    make_item(db, "MIC-001", "무선 마이크")
    make_item(db, "TRI-001", "카메라 삼각대")
    alice, admin = clients["alice"], clients["admin"]

    # 1) 검색 + 기간 조회
    start, end = now_utc() + timedelta(minutes=10), now_utc() + timedelta(hours=3)
    found = alice.get("/items", params={"q": "마이크", "start": iso(start), "end": iso(end)}).json()["items"]
    assert [i["asset_code"] for i in found] == ["MIC-001"]
    assert found[0]["period"]["available"] is True
    item_id = found[0]["id"]

    # 2) 예약 신청
    r = alice.post("/reservations", json={"item_id": item_id, "start_at": iso(start), "end_at": iso(end), "purpose": "학생회 회의"})
    assert r.status_code == 201
    rid = r.json()["reservation"]["id"]
    assert r.json()["reservation"]["status"] == "pending"

    # 3) 승인 → 아직 대여 전
    assert admin.post(f"/admin/reservations/{rid}/approve").json()["reservation"]["status"] == "approved"
    detail = alice.get(f"/items/{item_id}").json()
    assert detail["current_rental"] is None

    # 4) 인계 → 대여 중
    assert admin.post(f"/admin/reservations/{rid}/checkout").json()["reservation"]["status"] == "in_use"
    assert alice.get(f"/items/{item_id}").json()["current_rental"]["mine"] is True
    assert alice.get("/dashboard").json()["renting"][0]["id"] == rid

    # 5) 반납 요청 → 아직 대여 가능 상태 아님
    assert alice.post(f"/reservations/{rid}/return-request", json={"note": "선반에 둠"}).json()["reservation"]["status"] == "return_requested"
    assert alice.get(f"/items/{item_id}").json()["current_rental"] is not None

    # 6) 반납 완료
    done = admin.post(f"/admin/reservations/{rid}/return", json={"condition": "normal"}).json()["reservation"]
    assert done["status"] == "returned" and done["return_condition"] == "normal"

    # 7) "서버 재시작": 새 앱 인스턴스 + 새 로그인으로 다시 조회
    fresh = TestClient(create_app(run_startup=False))
    assert fresh.post("/auth/login", json={"email": users["alice"].email, "password": PW}).status_code == 200
    mine = fresh.get("/reservations/mine").json()["reservations"]
    assert mine[0]["id"] == rid and mine[0]["status"] == "returned"
    assert fresh.get(f"/items/{item_id}").json()["current_rental"] is None


def test_damage_report_flow(clients, db):
    item = make_item(db)
    rep = clients["alice"].post("/reports", json={"item_id": item.id, "description": "전원이 켜지지 않아요"})
    assert rep.status_code == 201
    rep_id = rep.json()["report"]["id"]
    r = clients["admin"].patch(
        f"/admin/reports/{rep_id}", json={"status": "in_progress", "admin_note": "배터리 교체 예정", "item_action": "set_repair"}
    )
    assert r.status_code == 200
    assert clients["alice"].get(f"/items/{item.id}").json()["item"]["status"] == "repair"
    r = clients["admin"].patch(f"/admin/reports/{rep_id}", json={"status": "resolved", "item_action": "set_normal"})
    assert r.json()["report"]["admin_note"] == "배터리 교체 예정"
    assert clients["alice"].get(f"/items/{item.id}").json()["item"]["status"] == "normal"
    mine = clients["alice"].get("/reports/mine").json()["reports"]
    assert mine[0]["status"] == "resolved"
    # 처리 시작된 신고는 접수로 되돌릴 수 없음
    assert clients["admin"].patch(f"/admin/reports/{rep_id}", json={"status": "received"}).status_code == 409
