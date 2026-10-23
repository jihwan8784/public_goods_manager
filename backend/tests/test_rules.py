"""예약 규칙·상태 전환 테스트 (서비스 계층 + API)."""

from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from pgm import services
from pgm.db import engine
from pgm.models import Reservation
from pgm.services import RuleError
from pgm.timeutil import SEOUL, now_utc

from .conftest import future, iso, make_item


def reserve(client, item_id, start, end, purpose="동아리 행사"):
    return client.post(
        "/reservations", json={"item_id": item_id, "start_at": iso(start), "end_at": iso(end), "purpose": purpose}
    )


def insert(db, item, user, start, end, status):
    r = Reservation(item_id=item.id, user_id=user.id, start_at=start, end_at=end, purpose="테스트", status=status)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


# ---------------------------------------------------------------- 기간 검증


def test_start_must_be_before_end(clients, item):
    r = reserve(clients["alice"], item.id, future(2), future(1))
    assert r.status_code == 422
    assert "시작 시각" in r.json()["detail"]
    r = reserve(clients["alice"], item.id, future(1), future(1))
    assert r.status_code == 422


def test_cannot_reserve_in_the_past(clients, item):
    past = now_utc() - timedelta(hours=2)
    r = reserve(clients["alice"], item.id, past, past + timedelta(hours=1))
    assert r.status_code == 422
    assert "지난 시간" in r.json()["detail"]


def test_naive_and_offset_times_are_treated_as_seoul(clients, item, db):
    start = future(0)
    # 같은 순간을 서로 다른 표기로 보낸다
    seoul_naive = start.astimezone(SEOUL).replace(tzinfo=None)  # "2026-10-24T10:00" 형식
    r = clients["alice"].post(
        "/reservations",
        json={
            "item_id": item.id,
            "start_at": seoul_naive.isoformat(),
            "end_at": (seoul_naive + timedelta(hours=1)).isoformat(),
            "purpose": "시간대 확인",
        },
    )
    assert r.status_code == 201, r.text
    saved = db.get(Reservation, r.json()["reservation"]["id"])
    assert saved.start_at == start  # UTC 기준 같은 순간


# ---------------------------------------------------------------- 겹침


def test_pending_requests_may_overlap(clients, item):
    assert reserve(clients["alice"], item.id, future(1), future(3)).status_code == 201
    assert reserve(clients["bob"], item.id, future(2), future(4)).status_code == 201


def test_overlapping_approval_is_rejected(clients, item):
    a = reserve(clients["alice"], item.id, future(1), future(3)).json()["reservation"]["id"]
    b = reserve(clients["bob"], item.id, future(2), future(4)).json()["reservation"]["id"]
    assert clients["admin"].post(f"/admin/reservations/{a}/approve").status_code == 200
    r = clients["admin"].post(f"/admin/reservations/{b}/approve")
    assert r.status_code == 409
    assert "겹쳐" in r.json()["detail"]


def test_new_request_blocked_by_approved_period(clients, item):
    a = reserve(clients["alice"], item.id, future(1), future(3)).json()["reservation"]["id"]
    clients["admin"].post(f"/admin/reservations/{a}/approve")
    r = reserve(clients["bob"], item.id, future(2), future(4))
    assert r.status_code == 409


def test_end_equal_to_next_start_is_allowed(clients, item):
    a = reserve(clients["alice"], item.id, future(1), future(3)).json()["reservation"]["id"]
    b = reserve(clients["bob"], item.id, future(3), future(5)).json()["reservation"]["id"]
    assert clients["admin"].post(f"/admin/reservations/{a}/approve").status_code == 200
    assert clients["admin"].post(f"/admin/reservations/{b}/approve").status_code == 200
    # 한 시각이라도 겹치면 불가
    c = reserve(clients["bob"], item.id, future(4.5), future(6))
    assert c.status_code == 409


def test_cancelled_and_rejected_do_not_occupy(clients, item):
    a = reserve(clients["alice"], item.id, future(1), future(3)).json()["reservation"]["id"]
    clients["admin"].post(f"/admin/reservations/{a}/approve")
    assert clients["alice"].post(f"/reservations/{a}/cancel", json={}).status_code == 200
    b = reserve(clients["bob"], item.id, future(1), future(3)).json()["reservation"]["id"]
    c = reserve(clients["alice"], item.id, future(1), future(3)).json()["reservation"]["id"]
    assert clients["admin"].post(f"/admin/reservations/{b}/reject", json={"reason": "중복"}).status_code == 200
    assert clients["admin"].post(f"/admin/reservations/{c}/approve").status_code == 200


def test_reject_requires_reason(clients, item):
    a = reserve(clients["alice"], item.id, future(1), future(3)).json()["reservation"]["id"]
    r = clients["admin"].post(f"/admin/reservations/{a}/reject", json={"reason": "  "})
    assert r.status_code == 422


def test_database_constraint_blocks_overlap_even_without_service(db, users, item):
    insert(db, item, users["alice"], future(1), future(3), "approved")
    with pytest.raises(IntegrityError):
        insert(db, item, users["bob"], future(2), future(4), "in_use")
    db.rollback()
    # 경계는 허용
    insert(db, item, users["bob"], future(3), future(4), "approved")


# ---------------------------------------------------------------- 수리 중 / 미반납


def test_repair_item_blocks_request_approval_and_checkout(clients, item, db):
    a = reserve(clients["alice"], item.id, now_utc() + timedelta(minutes=5), now_utc() + timedelta(hours=2))
    a_id = a.json()["reservation"]["id"]
    b_id = reserve(clients["bob"], item.id, future(10), future(11)).json()["reservation"]["id"]
    assert clients["admin"].post(f"/admin/reservations/{a_id}/approve").status_code == 200

    body = {"org_id": item.org_id, "asset_code": item.asset_code, "name": item.name, "category": "음향", "status": "repair"}
    r = clients["admin"].put(f"/admin/items/{item.id}", json=body)
    assert r.status_code == 200
    affected = {x["id"] for x in r.json()["affected"]}
    assert affected == {a_id, b_id}  # 영향받는 예약 표시

    assert clients["admin"].post(f"/admin/reservations/{b_id}/approve").status_code == 409
    r = clients["admin"].post(f"/admin/reservations/{a_id}/checkout")
    assert r.status_code == 409 and "수리 중" in r.json()["detail"]
    assert reserve(clients["alice"], item.id, future(20), future(21)).status_code == 409


def test_unreturned_item_blocks_next_checkout(clients, users, item, db):
    # 반납 기한이 지났지만 반납되지 않은 대여 (연체)
    overdue = insert(db, item, users["alice"], now_utc() - timedelta(days=2), now_utc() - timedelta(hours=1), "in_use")
    nxt = reserve(clients["bob"], item.id, now_utc() + timedelta(minutes=5), now_utc() + timedelta(hours=2))
    nxt_id = nxt.json()["reservation"]["id"]
    assert clients["admin"].post(f"/admin/reservations/{nxt_id}/approve").status_code == 200

    r = clients["admin"].post(f"/admin/reservations/{nxt_id}/checkout")
    assert r.status_code == 409 and "반납 완료되지 않았습니다" in r.json()["detail"]

    # 관리자 대시보드에 경고와 연체가 보인다
    dash = clients["admin"].get("/dashboard").json()["staff"]
    assert dash["counts"]["overdue"] == 1
    assert any(a["reservation"]["id"] == nxt_id for a in dash["alerts"])

    # 반납 요청만으로는 풀리지 않는다
    assert clients["alice"].post(f"/reservations/{overdue.id}/return-request", json={}).status_code == 200
    assert clients["admin"].post(f"/admin/reservations/{nxt_id}/checkout").status_code == 409

    # 관리자가 실물 확인 후 반납 완료하면 인계 가능
    r = clients["admin"].post(f"/admin/reservations/{overdue.id}/return", json={"condition": "normal"})
    assert r.status_code == 200
    assert clients["admin"].post(f"/admin/reservations/{nxt_id}/checkout").status_code == 200


def test_checkout_too_early_is_blocked(clients, item):
    a = reserve(clients["alice"], item.id, future(10), future(11)).json()["reservation"]["id"]
    clients["admin"].post(f"/admin/reservations/{a}/approve")
    r = clients["admin"].post(f"/admin/reservations/{a}/checkout")
    assert r.status_code == 409 and "분 전부터" in r.json()["detail"]


# ---------------------------------------------------------------- 상태 전환


def _in_use(clients, item):
    rid = reserve(clients["alice"], item.id, now_utc() + timedelta(minutes=5), now_utc() + timedelta(hours=2)).json()[
        "reservation"
    ]["id"]
    assert clients["admin"].post(f"/admin/reservations/{rid}/approve").status_code == 200
    assert clients["admin"].post(f"/admin/reservations/{rid}/checkout").status_code == 200
    return rid


def test_cannot_skip_states(clients, item):
    rid = reserve(clients["alice"], item.id, now_utc() + timedelta(minutes=5), now_utc() + timedelta(hours=2)).json()[
        "reservation"
    ]["id"]
    # 승인 전에 인계·반납 불가
    assert clients["admin"].post(f"/admin/reservations/{rid}/checkout").status_code == 409
    assert clients["admin"].post(f"/admin/reservations/{rid}/return", json={"condition": "normal"}).status_code == 409
    assert clients["alice"].post(f"/reservations/{rid}/return-request", json={}).status_code == 409
    # 승인만으로는 대여 중이 아니다
    clients["admin"].post(f"/admin/reservations/{rid}/approve")
    assert clients["alice"].get(f"/reservations/{rid}").json()["reservation"]["status"] == "approved"
    assert clients["alice"].post(f"/reservations/{rid}/return-request", json={}).status_code == 409
    # 이미 승인된 예약을 다시 승인·거절 불가
    assert clients["admin"].post(f"/admin/reservations/{rid}/approve").status_code == 409
    assert clients["admin"].post(f"/admin/reservations/{rid}/reject", json={"reason": "x"}).status_code == 409


def test_return_cannot_be_completed_twice(clients, item):
    rid = _in_use(clients, item)
    assert clients["alice"].post(f"/reservations/{rid}/cancel", json={}).status_code == 409  # 대여 중엔 취소 불가
    assert clients["alice"].post(f"/reservations/{rid}/return-request", json={}).status_code == 200
    assert clients["alice"].post(f"/reservations/{rid}/return-request", json={}).status_code == 409
    r1 = clients["admin"].post(f"/admin/reservations/{rid}/return", json={"condition": "normal"})
    assert r1.status_code == 200
    r2 = clients["admin"].post(f"/admin/reservations/{rid}/return", json={"condition": "normal"})
    assert r2.status_code == 409 and "이미 반납 완료" in r2.json()["detail"]
    assert clients["admin"].post(f"/admin/reservations/{rid}/checkout").status_code == 409


def test_concurrent_return_completion_happens_once(clients, users, item):
    rid = _in_use(clients, item)
    results = _race(lambda s: services.complete_return(s, users["admin"], rid, "needs_repair", None),
                    lambda s: services.complete_return(s, users["admin2"], rid, "needs_repair", None))
    assert sorted(results) == ["409", "ok"]
    # 고장 신고도 한 번만 생성
    reports = clients["admin"].get("/admin/reports").json()["reports"]
    assert len(reports) == 1


def test_return_needing_repair_sets_item_to_repair(clients, item):
    rid = _in_use(clients, item)
    later = reserve(clients["bob"], item.id, future(30), future(31)).json()["reservation"]["id"]
    r = clients["admin"].post(f"/admin/reservations/{rid}/return", json={"condition": "needs_repair", "note": "버튼 파손"})
    body = r.json()
    assert r.status_code == 200 and body["report_id"]
    assert [x["id"] for x in body["affected"]] == [later]
    assert clients["alice"].get(f"/items/{item.id}").json()["item"]["status"] == "repair"


# ---------------------------------------------------------------- 동시 승인


def _race(fn_a, fn_b):
    import threading

    barrier = threading.Barrier(2)
    results = []

    def run(fn):
        with Session(engine) as s:
            barrier.wait()
            try:
                fn(s)
                results.append("ok")
            except RuleError as e:
                results.append(str(e.status_code))

    threads = [threading.Thread(target=run, args=(f,)) for f in (fn_a, fn_b)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    return results


@pytest.mark.parametrize("round_", range(5))
def test_concurrent_approvals_never_double_book(db, users, item, round_):
    a = insert(db, item, users["alice"], future(1), future(3), "pending")
    b = insert(db, item, users["bob"], future(2), future(4), "pending")
    results = _race(
        lambda s: services.approve_reservation(s, users["admin"], a.id),
        lambda s: services.approve_reservation(s, users["admin2"], b.id),
    )
    assert sorted(results) == ["409", "ok"]
    with Session(engine) as s:
        approved = s.exec(select(Reservation).where(Reservation.status == "approved")).all()
        assert len(approved) == 1


def test_concurrent_approvals_over_http(clients, item):
    import threading

    a = reserve(clients["alice"], item.id, future(1), future(3)).json()["reservation"]["id"]
    b = reserve(clients["bob"], item.id, future(2), future(4)).json()["reservation"]["id"]
    barrier = threading.Barrier(2)
    codes = []

    def go(client, rid):
        barrier.wait()
        codes.append(client.post(f"/admin/reservations/{rid}/approve").status_code)

    ts = [threading.Thread(target=go, args=(clients["admin"], a)), threading.Thread(target=go, args=(clients["admin2"], b))]
    for t in ts:
        t.start()
    for t in ts:
        t.join(10)
    assert sorted(codes) == [200, 409]


def test_same_reservation_approved_twice_concurrently(db, users, item):
    a = insert(db, item, users["alice"], future(1), future(3), "pending")
    results = _race(
        lambda s: services.approve_reservation(s, users["admin"], a.id),
        lambda s: services.approve_reservation(s, users["admin2"], a.id),
    )
    assert sorted(results) == ["409", "ok"]


def test_other_items_are_independent(clients, db, item):
    other = make_item(db, "MIC-002")
    a = reserve(clients["alice"], item.id, future(1), future(3)).json()["reservation"]["id"]
    b = reserve(clients["bob"], other.id, future(1), future(3)).json()["reservation"]["id"]
    assert clients["admin"].post(f"/admin/reservations/{a}/approve").status_code == 200
    assert clients["admin"].post(f"/admin/reservations/{b}/approve").status_code == 200
