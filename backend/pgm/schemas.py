from datetime import datetime

from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from .models import DamageReport, Item, Reservation, User
from .services import STATUS_LABEL, is_overdue
from .timeutil import now_utc


# ---------------------------------------------------------------- 입력


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=1, max_length=72)


class ReservationIn(BaseModel):
    item_id: int
    start_at: datetime
    end_at: datetime
    purpose: str = Field(min_length=2, max_length=200)


class ReasonIn(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


class NoteIn(BaseModel):
    note: str | None = Field(default=None, max_length=300)


class ReturnIn(BaseModel):
    condition: str = Field(pattern="^(normal|needs_repair)$")
    note: str | None = Field(default=None, max_length=300)


class ReportIn(BaseModel):
    item_id: int
    description: str = Field(min_length=5, max_length=2000)
    reservation_id: int | None = None


class ReportUpdateIn(BaseModel):
    status: str = Field(pattern="^(received|in_progress|resolved|dismissed)$")
    admin_note: str | None = Field(default=None, max_length=2000)
    item_action: str = Field(default="none", pattern="^(none|set_repair|set_normal)$")


class ItemIn(BaseModel):
    asset_code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9\-_]*$")
    name: str = Field(min_length=1, max_length=80)
    category: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=4000)
    caution: str = Field(default="", max_length=4000)
    location: str = Field(default="", max_length=120)


class ItemUpdateIn(ItemIn):
    status: str = Field(pattern="^(normal|repair|retired)$")


class UserCreateIn(BaseModel):
    email: str = Field(min_length=3, max_length=120, pattern=r"^[^@\s]+@[^@\s]+$")
    name: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=72)
    role: str = Field(default="user", pattern="^(user|admin)$")


class UserUpdateIn(BaseModel):
    role: str | None = Field(default=None, pattern="^(user|admin)$")
    password: str | None = Field(default=None, min_length=8, max_length=72)


# ---------------------------------------------------------------- 출력


def user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role}


def item_brief(i: Item) -> dict:
    return {
        "id": i.id,
        "asset_code": i.asset_code,
        "name": i.name,
        "category": i.category,
        "location": i.location,
        "status": i.status,
        "has_image": i.image_data is not None,
        "image_version": i.image_version,
    }


def item_full(i: Item) -> dict:
    return {**item_brief(i), "description": i.description, "caution": i.caution, "updated_at": i.updated_at}


def reservation_out(r: Reservation, item: Item | None, user: User | None, now: datetime | None = None) -> dict:
    return {
        "id": r.id,
        "item": item_brief(item) if item else None,
        "user": {"id": user.id, "name": user.name, "email": user.email} if user else None,
        "start_at": r.start_at,
        "end_at": r.end_at,
        "purpose": r.purpose,
        "status": r.status,
        "status_label": STATUS_LABEL.get(r.status, r.status),
        "overdue": is_overdue(r, now),
        "reject_reason": r.reject_reason,
        "cancel_reason": r.cancel_reason,
        "decided_at": r.decided_at,
        "cancelled_at": r.cancelled_at,
        "checked_out_at": r.checked_out_at,
        "return_requested_at": r.return_requested_at,
        "return_request_note": r.return_request_note,
        "returned_at": r.returned_at,
        "return_condition": r.return_condition,
        "return_note": r.return_note,
        "created_at": r.created_at,
    }


def reservations_out(session: Session, rows: list[Reservation]) -> list[dict]:
    item_ids = {r.item_id for r in rows}
    user_ids = {r.user_id for r in rows}
    items = {i.id: i for i in session.exec(select(Item).where(col(Item.id).in_(item_ids))).all()} if rows else {}
    users = {u.id: u for u in session.exec(select(User).where(col(User.id).in_(user_ids))).all()} if rows else {}
    now = now_utc()
    return [reservation_out(r, items.get(r.item_id), users.get(r.user_id), now) for r in rows]


def report_out(rep: DamageReport, item: Item | None, reporter: User | None) -> dict:
    return {
        "id": rep.id,
        "item": item_brief(item) if item else None,
        "reporter": {"id": reporter.id, "name": reporter.name} if reporter else None,
        "reservation_id": rep.reservation_id,
        "description": rep.description,
        "status": rep.status,
        "admin_note": rep.admin_note,
        "created_at": rep.created_at,
        "updated_at": rep.updated_at,
    }


def reports_out(session: Session, rows: list[DamageReport]) -> list[dict]:
    if not rows:
        return []
    items = {i.id: i for i in session.exec(select(Item).where(col(Item.id).in_({r.item_id for r in rows}))).all()}
    users = {
        u.id: u for u in session.exec(select(User).where(col(User.id).in_({r.reporter_id for r in rows}))).all()
    }
    return [report_out(r, items.get(r.item_id), users.get(r.reporter_id)) for r in rows]
