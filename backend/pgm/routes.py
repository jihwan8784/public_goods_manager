from datetime import datetime, timedelta

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from . import config, services
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
    ROLE_ADMIN,
    UNRETURNED,
    DamageReport,
    Item,
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
    UserCreateIn,
    UserUpdateIn,
    item_brief,
    item_full,
    reports_out,
    reservations_out,
    user_out,
)
from .security import AdminUser, CurrentUser, SessionDep, create_token, hash_password, verify_password
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
    response.set_cookie(
        config.SESSION_COOKIE,
        create_token(user.id),
        max_age=config.SESSION_HOURS * 3600,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return {"user": user_out(user)}


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(config.SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(user: CurrentUser):
    return {"user": user_out(user)}


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
):
    query = select(Item)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.where(or_(col(Item.name).ilike(like), col(Item.asset_code).ilike(like)))
    if category:
        query = query.where(Item.category == category)
    if status:
        if status == ITEM_RETIRED and user.role != ROLE_ADMIN:
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
    out = []
    for i in items:
        r = rented.get(i.id)
        row = {
            **item_brief(i),
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
    is_admin = user.role == ROLE_ADMIN
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
        select(Item).where(Item.name == item.name, Item.id != item.id, Item.status != ITEM_RETIRED).order_by(Item.asset_code)
    ).all()
    return {
        "item": item_full(item),
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
    if not r or (r.user_id != user.id and user.role != ROLE_ADMIN):
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


def _admin_alerts(session, now: datetime) -> list[dict]:
    """인계가 막힌 확정 예약: 24시간 이내 시작인데 수리 중이거나 이전 대여가 미반납."""
    soon = session.exec(
        select(Reservation)
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


@router.get("/dashboard")
def dashboard(user: CurrentUser, session: SessionDep):
    now = now_utc()
    if user.role == ROLE_ADMIN:
        in_use = session.exec(
            select(func.count()).select_from(Reservation).where(col(Reservation.status).in_(UNRETURNED))
        ).one()
        pending = session.exec(
            select(func.count()).select_from(Reservation).where(Reservation.status == R_PENDING)
        ).one()
        return_requested = session.exec(
            select(func.count()).select_from(Reservation).where(Reservation.status == R_RETURN_REQUESTED)
        ).one()
        overdue_rows = list(
            session.exec(
                select(Reservation)
                .where(col(Reservation.status).in_(UNRETURNED), Reservation.end_at <= now)
                .order_by(Reservation.end_at)
            ).all()
        )
        open_reports = session.exec(
            select(func.count()).select_from(DamageReport).where(col(DamageReport.status).in_(REPORT_OPEN))
        ).one()
        today_end = now + timedelta(hours=24)
        handovers = list(
            session.exec(
                select(Reservation)
                .where(Reservation.status == R_APPROVED, Reservation.start_at <= today_end, Reservation.end_at > now)
                .order_by(Reservation.start_at)
            ).all()
        )
        return {
            "role": "admin",
            "counts": {
                "in_use": in_use,
                "pending": pending,
                "overdue": len(overdue_rows),
                "return_requested": return_requested,
                "open_reports": open_reports,
            },
            "overdue": reservations_out(session, overdue_rows[:10]),
            "handovers": reservations_out(session, handovers[:10]),
            "alerts": _admin_alerts(session, now),
        }

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
    return {
        "role": "user",
        "renting": [r for r in data if r["status"] in UNRETURNED],
        "upcoming": [r for r in data if r["status"] in (R_PENDING, R_APPROVED)],
        "recent": reservations_out(session, recent),
    }


# ================================================================ 관리자: 예약·대여


@router.get("/admin/reservations")
def admin_reservations(
    admin: AdminUser,
    session: SessionDep,
    status: str | None = None,
    q: str | None = Query(default=None, max_length=80),
    overdue: bool = False,
):
    query = select(Reservation)
    if overdue:
        query = query.where(col(Reservation.status).in_(UNRETURNED), Reservation.end_at <= now_utc())
    elif status:
        wanted = [s for s in status.split(",") if s in RESERVATION_STATUSES]
        if not wanted:
            raise HTTPException(422, "상태 값이 올바르지 않습니다.")
        query = query.where(col(Reservation.status).in_(wanted))
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = (
            query.join(Item, Item.id == Reservation.item_id)
            .join(User, User.id == Reservation.user_id)
            .where(or_(col(Item.name).ilike(like), col(Item.asset_code).ilike(like), col(User.name).ilike(like)))
        )
    order = col(Reservation.start_at).asc() if status and set(status.split(",")) <= {R_PENDING, R_APPROVED} else col(Reservation.start_at).desc()
    rows = list(session.exec(query.order_by(order).limit(300)).all())
    data = reservations_out(session, rows)
    now = now_utc()
    # 판단에 필요한 경고: 승인 대기는 확정 예약과의 충돌, 확정 예약은 인계 차단 사유
    for row, r in zip(data, rows):
        if r.status == R_PENDING:
            clash = services.find_overlapping(session, r.item_id, r.start_at, r.end_at, exclude_id=r.id)
            pending_clash = services.find_overlapping(
                session, r.item_id, r.start_at, r.end_at, statuses=(R_PENDING,), exclude_id=r.id
            )
            row["conflicts"] = [c.id for c in clash]
            row["pending_overlaps"] = [c.id for c in pending_clash]
            row["item_blocked"] = row["item"]["status"] != "normal" if row["item"] else False
        elif r.status == R_APPROVED:
            item = session.get(Item, r.item_id)
            row["blockers"] = services.checkout_blockers(session, r, item, now)
    return {"reservations": data}


@router.post("/admin/reservations/{reservation_id}/approve")
def admin_approve(reservation_id: int, admin: AdminUser, session: SessionDep):
    r = services.approve_reservation(session, admin, reservation_id)
    return {"reservation": reservations_out(session, [r])[0]}


@router.post("/admin/reservations/{reservation_id}/reject")
def admin_reject(reservation_id: int, body: ReasonIn, admin: AdminUser, session: SessionDep):
    r = services.reject_reservation(session, admin, reservation_id, body.reason or "")
    return {"reservation": reservations_out(session, [r])[0]}


@router.post("/admin/reservations/{reservation_id}/cancel")
def admin_cancel(reservation_id: int, body: ReasonIn, admin: AdminUser, session: SessionDep):
    r = services.cancel_reservation(session, admin, reservation_id, body.reason)
    return {"reservation": reservations_out(session, [r])[0]}


@router.post("/admin/reservations/{reservation_id}/checkout")
def admin_checkout(reservation_id: int, admin: AdminUser, session: SessionDep):
    r = services.checkout_reservation(session, admin, reservation_id)
    return {"reservation": reservations_out(session, [r])[0]}


@router.post("/admin/reservations/{reservation_id}/return")
def admin_return(reservation_id: int, body: ReturnIn, admin: AdminUser, session: SessionDep):
    res = services.complete_return(session, admin, reservation_id, body.condition, body.note)
    return {
        "reservation": reservations_out(session, [res.reservation])[0],
        "report_id": res.report.id if res.report else None,
        "affected": reservations_out(session, res.affected),
    }


# ================================================================ 관리자: 물품


@router.get("/admin/items")
def admin_items(admin: AdminUser, session: SessionDep):
    items = list(session.exec(select(Item).order_by(Item.category, Item.name, Item.asset_code)).all())
    counts = dict(
        session.exec(select(Reservation.item_id, func.count()).group_by(Reservation.item_id)).all()
    )
    rented = set(session.exec(select(Reservation.item_id).where(col(Reservation.status).in_(UNRETURNED))).all())
    open_reports = dict(
        session.exec(
            select(DamageReport.item_id, func.count())
            .where(col(DamageReport.status).in_(REPORT_OPEN))
            .group_by(DamageReport.item_id)
        ).all()
    )
    return {
        "items": [
            {
                **item_full(i),
                "reservation_count": counts.get(i.id, 0),
                "rented": i.id in rented,
                "open_reports": open_reports.get(i.id, 0),
            }
            for i in items
        ]
    }


def _code_taken(session, code: str, exclude_id: int | None = None) -> bool:
    q = select(Item).where(func.upper(Item.asset_code) == code.upper())
    if exclude_id:
        q = q.where(Item.id != exclude_id)
    return session.exec(q).first() is not None


@router.post("/admin/items", status_code=201)
def admin_create_item(body: ItemIn, admin: AdminUser, session: SessionDep):
    code = body.asset_code.strip().upper()
    if _code_taken(session, code):
        raise HTTPException(409, f"관리번호 {code}는 이미 사용 중입니다.")
    item = Item(
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
        raise HTTPException(409, f"관리번호 {code}는 이미 사용 중입니다.")
    session.refresh(item)
    return {"item": item_full(item)}


@router.put("/admin/items/{item_id}")
def admin_update_item(item_id: int, body: ItemUpdateIn, admin: AdminUser, session: SessionDep):
    item = _item_or_404(session, item_id)
    code = body.asset_code.strip().upper()
    if _code_taken(session, code, exclude_id=item_id):
        raise HTTPException(409, f"관리번호 {code}는 이미 사용 중입니다.")
    status_changed = item.status != body.status
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
        raise HTTPException(409, f"관리번호 {code}는 이미 사용 중입니다.")
    affected = []
    if status_changed:
        result = services.set_item_status(session, item_id, body.status)
        affected = reservations_out(session, result.affected)
    session.refresh(item)
    return {"item": item_full(item), "affected": affected}


@router.get("/admin/items/{item_id}/affected")
def admin_item_affected(item_id: int, admin: AdminUser, session: SessionDep):
    _item_or_404(session, item_id)
    return {"affected": reservations_out(session, services.affected_reservations(session, item_id))}


_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@router.post("/admin/items/{item_id}/image")
async def admin_upload_image(item_id: int, admin: AdminUser, session: SessionDep, file: UploadFile = File(...)):
    item = _item_or_404(session, item_id)
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
def admin_delete_image(item_id: int, admin: AdminUser, session: SessionDep):
    item = _item_or_404(session, item_id)
    item.image_data = None
    item.image_type = None
    item.image_version += 1
    item.updated_at = now_utc()
    session.commit()
    session.refresh(item)
    return {"item": item_full(item)}


@router.delete("/admin/items/{item_id}")
def admin_delete_item(item_id: int, admin: AdminUser, session: SessionDep):
    item = _item_or_404(session, item_id)
    has_res = session.exec(select(Reservation.id).where(Reservation.item_id == item_id).limit(1)).first()
    has_rep = session.exec(select(DamageReport.id).where(DamageReport.item_id == item_id).limit(1)).first()
    if has_res or has_rep:
        raise HTTPException(409, "대여·신고 기록이 있는 물품은 삭제할 수 없습니다. 보관 종료로 처리해 주세요.")
    session.delete(item)
    session.commit()
    return {"ok": True}


# ================================================================ 관리자: 고장 신고


@router.get("/admin/reports")
def admin_reports(admin: AdminUser, session: SessionDep, status: str | None = None):
    q = select(DamageReport)
    if status == "open":
        q = q.where(col(DamageReport.status).in_(REPORT_OPEN))
    elif status:
        if status not in REPORT_STATUSES:
            raise HTTPException(422, "상태 값이 올바르지 않습니다.")
        q = q.where(DamageReport.status == status)
    rows = list(session.exec(q.order_by(col(DamageReport.created_at).desc()).limit(300)).all())
    return {"reports": reports_out(session, rows)}


@router.patch("/admin/reports/{report_id}")
def admin_update_report(report_id: int, body: ReportUpdateIn, admin: AdminUser, session: SessionDep):
    rep, affected = services.update_report(session, admin, report_id, body.status, body.admin_note, body.item_action)
    return {"report": reports_out(session, [rep])[0], "affected": reservations_out(session, affected)}


# ================================================================ 관리자: 사용자


@router.get("/admin/users")
def admin_users(admin: AdminUser, session: SessionDep):
    users = session.exec(select(User).order_by(User.role, User.name)).all()
    return {"users": [user_out(u) for u in users]}


@router.post("/admin/users", status_code=201)
def admin_create_user(body: UserCreateIn, admin: AdminUser, session: SessionDep):
    email = body.email.strip().lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(409, "이미 등록된 아이디(이메일)입니다.")
    u = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password), role=body.role)
    session.add(u)
    session.commit()
    session.refresh(u)
    return {"user": user_out(u)}


@router.patch("/admin/users/{user_id}")
def admin_update_user(user_id: int, body: UserUpdateIn, admin: AdminUser, session: SessionDep):
    u = session.get(User, user_id)
    if not u:
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")
    if body.role and body.role != u.role:
        if u.id == admin.id:
            raise HTTPException(409, "자기 자신의 관리자 권한은 해제할 수 없습니다.")
        u.role = body.role
    if body.password:
        u.password_hash = hash_password(body.password)
    session.commit()
    session.refresh(u)
    return {"user": user_out(u)}
