import hmac
from datetime import datetime, timedelta

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import Integer, func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from . import config, services
from .access import StaffUser, can_manage, eligibility, is_staff, managed_org_ids, scope_filter
from .people import me_out, set_session_cookie
from .models import (
    ITEM_RETIRED,
    OCCUPYING,
    R_APPROVED,
    R_CANCELLED,
    R_IN_USE,
    R_PENDING,
    R_REJECTED,
    R_RETURN_REQUESTED,
    R_RETURNED,
    REPORT_OPEN,
    REPORT_STATUSES,
    RESERVATION_STATUSES,
    UNRETURNED,
    DamageReport,
    Item,
    Organization,
    Reservation,
    User,
)
from .schemas import (
    ItemIn,
    ItemUpdateIn,
    LoginIn,
    NoteIn,
    ReasonIn,
    ReportIn,
    ReportUpdateIn,
    ReservationIn,
    ReturnIn,
    item_brief,
    item_full,
    org_full,
    orgs_by_id,
    reports_out,
    reservations_out,
)
from .security import CurrentUser, SessionDep, hash_password, verify_password
from .timeutil import now_utc, to_utc

router = APIRouter()

_DUMMY_HASH = hash_password("timing-equalizer")


# ================================================================ 인증


@router.post("/auth/login")
def login(body: LoginIn, response: Response, session: SessionDep):
    email = body.email.strip().lower()
    user = session.exec(select(User).where(User.email == email)).first()
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok:
        raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다.")
    if user.suspended_at is not None:
        reason = f" (사유: {user.suspend_reason})" if user.suspend_reason else ""
        return JSONResponse(
            status_code=403,
            content={"detail": f"이용이 중지된 계정입니다{reason}. 관리자에게 문의해 주세요.", "code": "account_suspended"},
        )
    if user.email_verified_at is None:
        # 비밀번호가 맞을 때만 알려 준다 (가입 여부 노출 방지)
        return JSONResponse(
            status_code=403,
            content={"detail": "이메일 인증을 마쳐야 로그인할 수 있습니다. 메일함을 확인해 주세요.", "code": "email_not_verified"},
        )
    if config.ADMIN_ACCESS_CODE and is_staff(session, user):
        blocked = _check_admin_code(session, user, body.admin_code)
        if blocked:
            return blocked
    set_session_cookie(response, user)
    return {"user": me_out(session, user)}


def _check_admin_code(session, user: User, code: str | None) -> JSONResponse | None:
    """관리자 비밀 코드 확인. 통과하면 None, 막으면 보낼 응답."""
    now = now_utc()
    if user.admin_code_locked_until and user.admin_code_locked_until > now:
        mins = max(1, int((user.admin_code_locked_until - now).total_seconds() // 60) + 1)
        return JSONResponse(
            status_code=429,
            content={"detail": f"비밀 코드를 여러 번 틀려 관리자 로그인이 잠겼습니다. 약 {mins}분 후 다시 시도해 주세요.", "code": "admin_code_locked"},
        )
    if not code:
        return JSONResponse(
            status_code=401,
            content={"detail": "관리자 계정입니다. 관리자 비밀 코드를 입력해 주세요.", "code": "admin_code_required"},
        )
    if hmac.compare_digest(code.strip().encode(), config.ADMIN_ACCESS_CODE.encode()):
        if user.admin_code_failures or user.admin_code_locked_until:
            user.admin_code_failures = 0
            user.admin_code_locked_until = None
            session.commit()
        return None
    user.admin_code_failures = (user.admin_code_failures or 0) + 1
    left = config.ADMIN_CODE_MAX_FAILURES - user.admin_code_failures
    if left <= 0:
        user.admin_code_failures = 0
        user.admin_code_locked_until = now + timedelta(minutes=config.ADMIN_CODE_LOCK_MINUTES)
        session.commit()
        return JSONResponse(
            status_code=429,
            content={"detail": f"비밀 코드를 {config.ADMIN_CODE_MAX_FAILURES}번 틀려 {config.ADMIN_CODE_LOCK_MINUTES}분 동안 관리자 로그인이 잠겼습니다.", "code": "admin_code_locked"},
        )
    session.commit()
    return JSONResponse(
        status_code=401,
        content={"detail": f"관리자 비밀 코드가 올바르지 않습니다. ({left}번 더 틀리면 잠깁니다)", "code": "admin_code_invalid"},
    )


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(config.SESSION_COOKIE, path="/")
    return {"ok": True}


# ================================================================ 물품 (로그인 사용자)


def _item_or_404(session, item_id: int) -> Item:
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(404, "물품을 찾을 수 없습니다.")
    return item


@router.get("/items/categories")
def categories(user: CurrentUser, session: SessionDep):
    rows = session.exec(select(Item.category).distinct().order_by(Item.category)).all()
    return {"categories": list(rows)}


@router.get("/items")
def list_items(
    user: CurrentUser,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=80),
    category: str | None = None,
    status: str | None = Query(default=None, pattern="^(normal|repair|retired)$"),
    start: datetime | None = None,
    end: datetime | None = None,
    available_only: bool = False,
    org: int | None = None,
    eligible_only: bool = False,
):
    query = select(Item)
    if org:
        query = query.where(Item.org_id == org)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.where(or_(col(Item.name).ilike(like), col(Item.asset_code).ilike(like)))
    if category:
        query = query.where(Item.category == category)
    if status:
        if status == ITEM_RETIRED and not can_manage(session, user, org):
            raise HTTPException(403, "보관 종료 물품 목록은 관리자만 볼 수 있습니다.")
        query = query.where(Item.status == status)
    else:
        # 보관 종료 물품은 기본 목록에서 빼고, 관리자만 상태 필터로 따로 본다
        query = query.where(Item.status != ITEM_RETIRED)
    items = list(session.exec(query.order_by(Item.name, Item.asset_code)).all())
    ids = [i.id for i in items]

    period = None
    if start or end:
        if not (start and end):
            raise HTTPException(422, "기간 조회에는 시작과 종료 시각이 모두 필요합니다.")
        s, e = to_utc(start), to_utc(end)
        if s >= e:
            raise HTTPException(422, "시작 시각은 종료 시각보다 빨라야 합니다.")
        period = (s, e)

    rented: dict[int, Reservation] = {}
    busy: set[int] = set()
    if ids:
        for r in session.exec(
            select(Reservation).where(col(Reservation.item_id).in_(ids), col(Reservation.status).in_(UNRETURNED))
        ).all():
            rented[r.item_id] = r
        if period:
            busy = set(
                session.exec(
                    select(Reservation.item_id).where(
                        col(Reservation.item_id).in_(ids),
                        col(Reservation.status).in_(OCCUPYING),
                        Reservation.start_at < period[1],
                        Reservation.end_at > period[0],
                    )
                ).all()
            )
    now = now_utc()
    orgs = orgs_by_id(session, (i.org_id for i in items))
    out = []
    for i in items:
        r = rented.get(i.id)
        ok, why = eligibility(user, i, orgs.get(i.org_id))
        if eligible_only and not ok:
            continue
        row = {
            **item_brief(i, orgs.get(i.org_id)),
            "eligible": ok,
            "eligible_reason": why,
            "rented": r is not None,
            "rented_due": r.end_at if r else None,
            "rented_overdue": bool(r and services.is_overdue(r, now)),
        }
        if period:
            if i.status != "normal":
                reason = "수리 중" if i.status == "repair" else "보관 종료"
                row["period"] = {"available": False, "reason": reason}
            elif i.id in busy:
                row["period"] = {"available": False, "reason": "선택 기간에 확정된 예약 있음"}
            else:
                row["period"] = {"available": True, "reason": None}
            if available_only and not row["period"]["available"]:
                continue
        out.append(row)
    return {"items": out}


@router.get("/items/{item_id}")
def item_detail(item_id: int, user: CurrentUser, session: SessionDep):
    item = _item_or_404(session, item_id)
    now = now_utc()
    rows = session.exec(
        select(Reservation)
        .where(
            Reservation.item_id == item_id,
            col(Reservation.status).in_(OCCUPYING),
            or_(Reservation.end_at > now, col(Reservation.status).in_(UNRETURNED)),
        )
        .order_by(Reservation.start_at)
    ).all()
    is_admin = can_manage(session, user, item.org_id)
    users = {}
    if is_admin and rows:
        users = {u.id: u for u in session.exec(select(User).where(col(User.id).in_({r.user_id for r in rows}))).all()}
    busy = []
    current = None
    for r in rows:
        entry = {
            "start_at": r.start_at,
            "end_at": r.end_at,
            "status": r.status,
            "status_label": services.STATUS_LABEL[r.status],
            "overdue": services.is_overdue(r, now),
            "mine": r.user_id == user.id,
        }
        if is_admin:
            entry["reservation_id"] = r.id
            entry["user_name"] = users[r.user_id].name if r.user_id in users else None
        busy.append(entry)
        if r.status in UNRETURNED:
            current = entry
    siblings = session.exec(
        select(Item)
        .where(Item.name == item.name, Item.org_id == item.org_id, Item.id != item.id, Item.status != ITEM_RETIRED)
        .order_by(Item.asset_code)
    ).all()
    org = session.get(Organization, item.org_id) if item.org_id else None
    ok, why = eligibility(user, item, org)
    return {
        "item": item_full(item, org),
        "org": org_full(org) if org else None,
        "eligible": ok,
        "eligible_reason": why,
        "can_manage": is_admin,
        "current_rental": current,
        "busy": busy,
        "siblings": [item_brief(s) for s in siblings],
    }


@router.get("/items/{item_id}/availability")
def item_availability(item_id: int, start: datetime, end: datetime, user: CurrentUser, session: SessionDep):
    item = _item_or_404(session, item_id)
    a = services.check_availability(session, item, start, end)
    if a.available and to_utc(start) < now_utc() - timedelta(seconds=config.PAST_TOLERANCE_SECONDS):
        return {"available": False, "reason": "지난 시간으로는 예약할 수 없습니다."}
    return {"available": a.available, "reason": a.reason}


@router.get("/items/{item_id}/image")
def item_image(item_id: int, user: CurrentUser, session: SessionDep):
    item = _item_or_404(session, item_id)
    if item.image_data is None:
        raise HTTPException(404, "등록된 사진이 없습니다.")
    return Response(
        content=item.image_data,
        media_type=item.image_type or "image/jpeg",
        headers={"Cache-Control": "private, max-age=86400"},
    )


# ================================================================ 예약 (본인)


@router.post("/reservations", status_code=201)
def create_reservation(body: ReservationIn, user: CurrentUser, session: SessionDep):
    r = services.create_reservation(session, user, body.item_id, body.start_at, body.end_at, body.purpose)
    return {"reservation": reservations_out(session, [r])[0]}


@router.get("/reservations/mine")
def my_reservations(
    user: CurrentUser,
    session: SessionDep,
    scope: str = Query(default="all", pattern="^(active|past|all)$"),
):
    q = select(Reservation).where(Reservation.user_id == user.id)
    if scope == "active":
        q = q.where(col(Reservation.status).in_((R_PENDING, R_APPROVED, R_IN_USE, R_RETURN_REQUESTED)))
    elif scope == "past":
        q = q.where(col(Reservation.status).in_((R_RETURNED, R_REJECTED, R_CANCELLED)))
    rows = list(session.exec(q.order_by(col(Reservation.start_at).desc()).limit(300)).all())
    return {"reservations": reservations_out(session, rows)}


@router.get("/reservations/{reservation_id}")
def reservation_detail(reservation_id: int, user: CurrentUser, session: SessionDep):
    r = session.get(Reservation, reservation_id)
    item = session.get(Item, r.item_id) if r else None
    if not r or (r.user_id != user.id and not can_manage(session, user, item.org_id if item else None)):
        raise HTTPException(404, "예약을 찾을 수 없습니다.")
    return {"reservation": reservations_out(session, [r])[0]}


@router.post("/reservations/{reservation_id}/cancel")
def cancel_reservation(reservation_id: int, body: ReasonIn, user: CurrentUser, session: SessionDep):
    r = services.cancel_reservation(session, user, reservation_id, body.reason)
    return {"reservation": reservations_out(session, [r])[0]}


@router.post("/reservations/{reservation_id}/return-request")
def return_request(reservation_id: int, body: NoteIn, user: CurrentUser, session: SessionDep):
    r = services.request_return(session, user, reservation_id, body.note)
    return {"reservation": reservations_out(session, [r])[0]}


# ================================================================ 고장 신고 (본인)


@router.post("/reports", status_code=201)
def create_report(body: ReportIn, user: CurrentUser, session: SessionDep):
    rep = services.create_report(session, user, body.item_id, body.description, body.reservation_id)
    return {"report": reports_out(session, [rep])[0]}


@router.get("/reports/mine")
def my_reports(user: CurrentUser, session: SessionDep):
    rows = list(
        session.exec(
            select(DamageReport)
            .where(DamageReport.reporter_id == user.id)
            .order_by(col(DamageReport.created_at).desc())
            .limit(100)
        ).all()
    )
    return {"reports": reports_out(session, rows)}


# ================================================================ 대시보드


def _res_in_scope(query, ids):
    """예약 쿼리를 관리 기관의 물품으로 한정"""
    if ids is None:
        return query
    return query.join(Item, Item.id == Reservation.item_id).where(col(Item.org_id).in_(ids or {-1}))


def _admin_alerts(session, now: datetime, ids) -> list[dict]:
    """인계가 막힌 확정 예약: 24시간 이내 시작인데 수리 중이거나 이전 대여가 미반납."""
    soon = session.exec(
        _res_in_scope(select(Reservation), ids)
        .where(
            Reservation.status == R_APPROVED,
            Reservation.start_at <= now + timedelta(hours=24),
            Reservation.end_at > now,
        )
        .order_by(Reservation.start_at)
    ).all()
    alerts = []
    for r in soon:
        item = session.get(Item, r.item_id)
        blockers = [
            b
            for b in services.checkout_blockers(session, r, item, now)
            if not b.startswith("예약 시작")  # 아직 이른 것은 경고가 아님
        ]
        if blockers:
            alerts.append({"reservation": reservations_out(session, [r])[0], "blockers": blockers})
    return alerts


def _count(session, query) -> int:
    return session.exec(select(func.count()).select_from(query.subquery())).one()


@router.get("/dashboard")
def dashboard(user: CurrentUser, session: SessionDep):
    now = now_utc()
    mine = list(
        session.exec(
            select(Reservation)
            .where(
                Reservation.user_id == user.id,
                col(Reservation.status).in_((R_PENDING, R_APPROVED, R_IN_USE, R_RETURN_REQUESTED)),
            )
            .order_by(Reservation.start_at)
        ).all()
    )
    recent = list(
        session.exec(
            select(Reservation)
            .where(
                Reservation.user_id == user.id,
                col(Reservation.status).in_((R_REJECTED, R_CANCELLED, R_RETURNED)),
                Reservation.updated_at >= now - timedelta(days=7),
            )
            .order_by(col(Reservation.updated_at).desc())
            .limit(5)
        ).all()
    )
    data = reservations_out(session, mine)
    out = {
        "renting": [r for r in data if r["status"] in UNRETURNED],
        "upcoming": [r for r in data if r["status"] in (R_PENDING, R_APPROVED)],
        "recent": reservations_out(session, recent),
        "staff": None,
    }
    ids = managed_org_ids(session, user)
    if ids is None or ids:
        base = _res_in_scope(select(Reservation.id), ids)
        overdue_rows = list(
            session.exec(
                _res_in_scope(select(Reservation), ids)
                .where(col(Reservation.status).in_(UNRETURNED), Reservation.end_at <= now)
                .order_by(Reservation.end_at)
            ).all()
        )
        rep_q = select(DamageReport.id).where(col(DamageReport.status).in_(REPORT_OPEN))
        if ids is not None:
            rep_q = rep_q.join(Item, Item.id == DamageReport.item_id).where(col(Item.org_id).in_(ids or {-1}))
        stu_q = select(User.id).where(User.is_student == True, User.student_status == "pending")  # noqa: E712
        if ids is not None:
            stu_q = stu_q.where(col(User.school_id).in_(ids or {-1}))
        handovers = list(
            session.exec(
                _res_in_scope(select(Reservation), ids)
                .where(Reservation.status == R_APPROVED, Reservation.start_at <= now + timedelta(hours=24), Reservation.end_at > now)
                .order_by(Reservation.start_at)
            ).all()
        )
        out["staff"] = {
            "counts": {
                "in_use": _count(session, base.where(col(Reservation.status).in_(UNRETURNED))),
                "pending": _count(session, base.where(Reservation.status == R_PENDING)),
                "overdue": len(overdue_rows),
                "return_requested": _count(session, base.where(Reservation.status == R_RETURN_REQUESTED)),
                "open_reports": _count(session, rep_q),
                "pending_students": _count(session, stu_q),
            },
            "overdue": reservations_out(session, overdue_rows[:10]),
            "handovers": reservations_out(session, handovers[:10]),
            "alerts": _admin_alerts(session, now, ids),
        }
    return out


# ================================================================ 관리자: 예약·대여 (관리 기관 한정)


@router.get("/admin/reservations")
def admin_reservations(
    staff: StaffUser,
    session: SessionDep,
    status: str | None = None,
    q: str | None = Query(default=None, max_length=80),
    overdue: bool = False,
    org: int | None = None,
):
    ids = managed_org_ids(session, staff)
    query = select(Reservation).join(Item, Item.id == Reservation.item_id)
    if ids is not None:
        query = query.where(col(Item.org_id).in_(ids or {-1}))
    if org:
        query = query.where(Item.org_id == org)
    if overdue:
        query = query.where(col(Reservation.status).in_(UNRETURNED), Reservation.end_at <= now_utc())
    elif status:
        wanted = [s for s in status.split(",") if s in RESERVATION_STATUSES]
        if not wanted:
            raise HTTPException(422, "상태 값이 올바르지 않습니다.")
        query = query.where(col(Reservation.status).in_(wanted))
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.join(User, User.id == Reservation.user_id).where(
            or_(col(Item.name).ilike(like), col(Item.asset_code).ilike(like), col(User.name).ilike(like))
        )
    order = (
        col(Reservation.start_at).asc()
        if status and set(status.split(",")) <= {R_PENDING, R_APPROVED}
        else col(Reservation.start_at).desc()
    )
    rows = list(session.exec(query.order_by(order).limit(300)).all())
    data = reservations_out(session, rows)
    now = now_utc()
    # 판단에 필요한 경고: 승인 대기는 확정 예약과의 충돌·대여 자격, 확정 예약은 인계 차단 사유
    users = {u.id: u for u in session.exec(select(User).where(col(User.id).in_({r.user_id for r in rows} or {-1}))).all()}
    for row, r in zip(data, rows):
        if r.status == R_PENDING:
            item = session.get(Item, r.item_id)
            clash = services.find_overlapping(session, r.item_id, r.start_at, r.end_at, exclude_id=r.id)
            pending_clash = services.find_overlapping(
                session, r.item_id, r.start_at, r.end_at, statuses=(R_PENDING,), exclude_id=r.id
            )
            row["conflicts"] = [c.id for c in clash]
            row["pending_overlaps"] = [c.id for c in pending_clash]
            row["item_blocked"] = row["item"]["status"] != "normal" if row["item"] else False
            ok, why = eligibility(users[r.user_id], item, session.get(Organization, item.org_id) if item.org_id else None)
            row["ineligible_reason"] = None if ok else why
        elif r.status == R_APPROVED:
            item = session.get(Item, r.item_id)
            row["blockers"] = services.checkout_blockers(session, r, item, now)
    return {"reservations": data}


@router.post("/admin/reservations/{reservation_id}/approve")
def admin_approve(reservation_id: int, staff: StaffUser, session: SessionDep):
    r = services.approve_reservation(session, staff, reservation_id)
    return {"reservation": reservations_out(session, [r])[0]}


@router.post("/admin/reservations/{reservation_id}/reject")
def admin_reject(reservation_id: int, body: ReasonIn, staff: StaffUser, session: SessionDep):
    r = services.reject_reservation(session, staff, reservation_id, body.reason or "")
    return {"reservation": reservations_out(session, [r])[0]}


@router.post("/admin/reservations/{reservation_id}/cancel")
def admin_cancel(reservation_id: int, body: ReasonIn, staff: StaffUser, session: SessionDep):
    r = services.cancel_reservation(session, staff, reservation_id, body.reason)
    return {"reservation": reservations_out(session, [r])[0]}


@router.post("/admin/reservations/{reservation_id}/checkout")
def admin_checkout(reservation_id: int, staff: StaffUser, session: SessionDep):
    r = services.checkout_reservation(session, staff, reservation_id)
    return {"reservation": reservations_out(session, [r])[0]}


@router.post("/admin/reservations/{reservation_id}/return")
def admin_return(reservation_id: int, body: ReturnIn, staff: StaffUser, session: SessionDep):
    res = services.complete_return(session, staff, reservation_id, body.condition, body.note)
    return {
        "reservation": reservations_out(session, [res.reservation])[0],
        "report_id": res.report.id if res.report else None,
        "affected": reservations_out(session, res.affected),
    }


# ================================================================ 관리자: 물품 (관리 기관 한정)


def _managed_item(session, staff: User, item_id: int) -> Item:
    item = _item_or_404(session, item_id)
    if not can_manage(session, staff, item.org_id):
        raise HTTPException(404, "물품을 찾을 수 없습니다.")
    return item


def _require_org(session, staff: User, org_id: int) -> Organization:
    org = session.get(Organization, org_id)
    if not org:
        raise HTTPException(422, "기관을 선택해 주세요.")
    if not can_manage(session, staff, org_id):
        raise HTTPException(403, "이 기관의 관리자만 물품을 등록·수정할 수 있습니다.")
    return org


@router.get("/admin/items")
def admin_items(staff: StaffUser, session: SessionDep, org: int | None = None):
    ids = managed_org_ids(session, staff)
    query = scope_filter(select(Item), Item.org_id, ids)
    if org:
        query = query.where(Item.org_id == org)
    items = list(session.exec(query.order_by(Item.category, Item.name, Item.asset_code)).all())
    item_ids = [i.id for i in items] or [-1]
    counts = dict(
        session.exec(
            select(Reservation.item_id, func.count()).where(col(Reservation.item_id).in_(item_ids)).group_by(Reservation.item_id)
        ).all()
    )
    rented = set(
        session.exec(
            select(Reservation.item_id).where(col(Reservation.item_id).in_(item_ids), col(Reservation.status).in_(UNRETURNED))
        ).all()
    )
    open_reports = dict(
        session.exec(
            select(DamageReport.item_id, func.count())
            .where(col(DamageReport.item_id).in_(item_ids), col(DamageReport.status).in_(REPORT_OPEN))
            .group_by(DamageReport.item_id)
        ).all()
    )
    orgs = orgs_by_id(session, (i.org_id for i in items))
    return {
        "items": [
            {
                **item_full(i, orgs.get(i.org_id)),
                "reservation_count": counts.get(i.id, 0),
                "rented": i.id in rented,
                "open_reports": open_reports.get(i.id, 0),
            }
            for i in items
        ]
    }


def next_asset_code(session, org_id: int) -> str:
    """기관별 다음 관리번호 (0001, 0002, …). 기관 행을 잠가 동시에 등록해도 번호가 겹치지 않는다.
    예전 방식 관리번호(MIC-001 등)는 건너뛰고 숫자만으로 된 번호 중 가장 큰 값 + 1."""
    session.exec(select(Organization.id).where(Organization.id == org_id).with_for_update()).first()
    biggest = session.exec(
        select(func.max(func.cast(Item.asset_code, Integer))).where(
            Item.org_id == org_id, col(Item.asset_code).regexp_match(r"^\d{1,9}$")
        )
    ).one()
    return f"{(biggest or 0) + 1:04d}"


@router.post("/admin/items", status_code=201)
def admin_create_item(body: ItemIn, staff: StaffUser, session: SessionDep):
    org = _require_org(session, staff, body.org_id)
    code = next_asset_code(session, org.id)
    item = Item(
        org_id=org.id,
        access=body.access,
        asset_code=code,
        name=body.name.strip(),
        category=body.category.strip(),
        description=body.description.strip(),
        caution=body.caution.strip(),
        location=body.location.strip(),
    )
    session.add(item)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "관리번호를 정하는 중 충돌이 났습니다. 다시 시도해 주세요.")
    session.refresh(item)
    return {"item": item_full(item, org)}


@router.put("/admin/items/{item_id}")
def admin_update_item(item_id: int, body: ItemUpdateIn, staff: StaffUser, session: SessionDep):
    item = _managed_item(session, staff, item_id)
    org = _require_org(session, staff, body.org_id)
    if org.id != item.org_id:
        has_open = session.exec(
            select(Reservation.id).where(
                Reservation.item_id == item_id, col(Reservation.status).in_((R_PENDING,) + OCCUPYING)
            )
        ).first()
        if has_open:
            raise HTTPException(409, "진행 중인 예약이 있는 물품은 다른 기관으로 옮길 수 없습니다.")
    # 관리번호는 직접 바꾸지 않는다. 다른 기관으로 옮기면 그 기관의 다음 번호를 새로 받는다.
    code = item.asset_code if org.id == item.org_id else next_asset_code(session, org.id)
    status_changed = item.status != body.status
    item.org_id = org.id
    item.access = body.access
    item.asset_code = code
    item.name = body.name.strip()
    item.category = body.category.strip()
    item.description = body.description.strip()
    item.caution = body.caution.strip()
    item.location = body.location.strip()
    item.updated_at = now_utc()
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "관리번호를 정하는 중 충돌이 났습니다. 다시 시도해 주세요.")
    affected = []
    if status_changed:
        result = services.set_item_status(session, item_id, body.status)
        affected = reservations_out(session, result.affected)
    session.refresh(item)
    return {"item": item_full(item, org), "affected": affected}


@router.get("/admin/items/{item_id}/affected")
def admin_item_affected(item_id: int, staff: StaffUser, session: SessionDep):
    _managed_item(session, staff, item_id)
    return {"affected": reservations_out(session, services.affected_reservations(session, item_id))}


_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@router.post("/admin/items/{item_id}/image")
async def admin_upload_image(item_id: int, staff: StaffUser, session: SessionDep, file: UploadFile = File(...)):
    item = _managed_item(session, staff, item_id)
    if file.content_type not in _IMAGE_TYPES:
        raise HTTPException(422, "JPG, PNG, WEBP, GIF 이미지만 올릴 수 있습니다.")
    data = await file.read(config.MAX_IMAGE_BYTES + 1)
    if len(data) > config.MAX_IMAGE_BYTES:
        raise HTTPException(413, "사진은 2MB 이하로 올려 주세요.")
    if not data:
        raise HTTPException(422, "빈 파일입니다.")
    item.image_data = data
    item.image_type = file.content_type
    item.image_version += 1
    item.updated_at = now_utc()
    session.commit()
    session.refresh(item)
    return {"item": item_full(item)}


@router.delete("/admin/items/{item_id}/image")
def admin_delete_image(item_id: int, staff: StaffUser, session: SessionDep):
    item = _managed_item(session, staff, item_id)
    item.image_data = None
    item.image_type = None
    item.image_version += 1
    item.updated_at = now_utc()
    session.commit()
    session.refresh(item)
    return {"item": item_full(item)}


@router.delete("/admin/items/{item_id}")
def admin_delete_item(item_id: int, staff: StaffUser, session: SessionDep):
    item = _managed_item(session, staff, item_id)
    has_res = session.exec(select(Reservation.id).where(Reservation.item_id == item_id).limit(1)).first()
    has_rep = session.exec(select(DamageReport.id).where(DamageReport.item_id == item_id).limit(1)).first()
    if has_res or has_rep:
        raise HTTPException(409, "대여·신고 기록이 있는 물품은 삭제할 수 없습니다. 보관 종료로 처리해 주세요.")
    session.delete(item)
    session.commit()
    return {"ok": True}


# ================================================================ 관리자: 고장 신고 (관리 기관 한정)


@router.get("/admin/reports")
def admin_reports(staff: StaffUser, session: SessionDep, status: str | None = None):
    ids = managed_org_ids(session, staff)
    q = select(DamageReport)
    if ids is not None:
        q = q.join(Item, Item.id == DamageReport.item_id).where(col(Item.org_id).in_(ids or {-1}))
    if status == "open":
        q = q.where(col(DamageReport.status).in_(REPORT_OPEN))
    elif status:
        if status not in REPORT_STATUSES:
            raise HTTPException(422, "상태 값이 올바르지 않습니다.")
        q = q.where(DamageReport.status == status)
    rows = list(session.exec(q.order_by(col(DamageReport.created_at).desc()).limit(300)).all())
    return {"reports": reports_out(session, rows)}


@router.patch("/admin/reports/{report_id}")
def admin_update_report(report_id: int, body: ReportUpdateIn, staff: StaffUser, session: SessionDep):
    rep, affected = services.update_report(session, staff, report_id, body.status, body.admin_note, body.item_action)
    return {"report": reports_out(session, [rep])[0], "affected": reservations_out(session, affected)}
