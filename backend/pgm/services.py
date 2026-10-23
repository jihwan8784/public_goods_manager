"""예약·대여·반납·고장 처리 규칙.

모든 상태 변경은 이 모듈을 통해서만 일어난다.
- 상태 변경 전 대상 예약 행을 SELECT ... FOR UPDATE 로 잠근다.
- 기간 점유가 생기는 작업(승인, 인계)은 물품 행도 잠가서 같은 물품의 처리를 직렬화한다.
- 잠금 순서는 항상 예약 → 물품 순서로 고정해 교착 상태를 피한다.
- 마지막 안전장치로 DB 배제 제약(pgm_reservation_no_overlap)이 겹침을 막는다.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from . import config
from .models import (
    COND_NEEDS_REPAIR,
    COND_NORMAL,
    ITEM_NORMAL,
    ITEM_REPAIR,
    ITEM_RETIRED,
    OCCUPYING,
    R_APPROVED,
    R_CANCELLED,
    R_IN_USE,
    R_PENDING,
    R_REJECTED,
    R_RETURN_REQUESTED,
    R_RETURNED,
    REPORT_IN_PROGRESS,
    REPORT_OPEN,
    REPORT_RECEIVED,
    REPORT_STATUSES,
    ROLE_ADMIN,
    UNRETURNED,
    DamageReport,
    Item,
    Reservation,
    User,
)
from .timeutil import fmt_seoul, now_utc, to_utc

STATUS_LABEL = {
    R_PENDING: "승인 대기",
    R_APPROVED: "예약 확정",
    R_REJECTED: "거절",
    R_CANCELLED: "취소",
    R_IN_USE: "대여 중",
    R_RETURN_REQUESTED: "반납 요청",
    R_RETURNED: "반납 완료",
}


class RuleError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _not_found(what: str = "예약") -> RuleError:
    return RuleError(404, f"{what}을(를) 찾을 수 없습니다.")


def _bad_state(r: Reservation, action: str) -> RuleError:
    return RuleError(409, f"현재 상태({STATUS_LABEL.get(r.status, r.status)})에서는 {action}할 수 없습니다.")


# ---------------------------------------------------------------- 조회 도우미


def find_overlapping(
    session: Session,
    item_id: int,
    start: datetime,
    end: datetime,
    statuses=OCCUPYING,
    exclude_id: int | None = None,
) -> list[Reservation]:
    """[start, end) 와 겹치는 예약. 끝 시각 == 다음 시작 시각은 겹침이 아니다."""
    q = select(Reservation).where(
        Reservation.item_id == item_id,
        col(Reservation.status).in_(statuses),
        Reservation.start_at < end,
        Reservation.end_at > start,
    )
    if exclude_id is not None:
        q = q.where(Reservation.id != exclude_id)
    return list(session.exec(q.order_by(Reservation.start_at)).all())


def unreturned_rentals(
    session: Session, item_id: int, exclude_id: int | None = None
) -> list[Reservation]:
    q = select(Reservation).where(
        Reservation.item_id == item_id, col(Reservation.status).in_(UNRETURNED)
    )
    if exclude_id is not None:
        q = q.where(Reservation.id != exclude_id)
    return list(session.exec(q).all())


def affected_reservations(session: Session, item_id: int) -> list[Reservation]:
    """물품이 수리·보관 종료로 바뀔 때 영향을 받는 앞으로의 예약."""
    q = select(Reservation).where(
        Reservation.item_id == item_id,
        col(Reservation.status).in_((R_PENDING, R_APPROVED)),
        Reservation.end_at > now_utc(),
    )
    return list(session.exec(q.order_by(Reservation.start_at)).all())


def is_overdue(r: Reservation, now: datetime | None = None) -> bool:
    return r.status in UNRETURNED and to_utc(r.end_at) <= (now or now_utc())


@dataclass
class Availability:
    available: bool
    reason: str | None = None


def check_availability(session: Session, item: Item, start: datetime, end: datetime) -> Availability:
    start, end = to_utc(start), to_utc(end)
    if start >= end:
        return Availability(False, "시작 시각은 종료 시각보다 빨라야 합니다.")
    if item.status == ITEM_RETIRED:
        return Availability(False, "보관 종료된 물품입니다.")
    if item.status == ITEM_REPAIR:
        return Availability(False, "수리 중인 물품입니다.")
    clash = find_overlapping(session, item.id, start, end)
    if clash:
        c = clash[0]
        return Availability(
            False, f"이미 확정된 예약과 겹칩니다 ({fmt_seoul(c.start_at)} ~ {fmt_seoul(c.end_at)})."
        )
    return Availability(True)


# ---------------------------------------------------------------- 예약 신청 / 취소


def validate_period(start: datetime, end: datetime, now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or now_utc()
    start, end = to_utc(start), to_utc(end)
    if start >= end:
        raise RuleError(422, "시작 시각은 종료 시각보다 빨라야 합니다.")
    if start < now - timedelta(seconds=config.PAST_TOLERANCE_SECONDS):
        raise RuleError(422, "지난 시간으로는 예약할 수 없습니다.")
    if end - start > timedelta(days=config.MAX_RESERVATION_DAYS):
        raise RuleError(422, f"한 번에 최대 {config.MAX_RESERVATION_DAYS}일까지 예약할 수 있습니다.")
    if start > now + timedelta(days=config.MAX_ADVANCE_DAYS):
        raise RuleError(422, f"{config.MAX_ADVANCE_DAYS}일 이내의 기간만 예약할 수 있습니다.")
    return start, end


def create_reservation(
    session: Session, user: User, item_id: int, start: datetime, end: datetime, purpose: str
) -> Reservation:
    start, end = validate_period(start, end)
    purpose = purpose.strip()
    if len(purpose) < 2:
        raise RuleError(422, "사용 목적을 2자 이상 입력해 주세요.")
    item = session.get(Item, item_id)
    if not item:
        raise _not_found("물품")
    avail = check_availability(session, item, start, end)
    if not avail.available:
        raise RuleError(409, avail.reason or "예약할 수 없는 기간입니다.")
    r = Reservation(item_id=item.id, user_id=user.id, start_at=start, end_at=end, purpose=purpose)
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


def _lock_reservation(session: Session, reservation_id: int) -> Reservation:
    r = session.exec(
        select(Reservation).where(Reservation.id == reservation_id).with_for_update()
    ).first()
    if not r:
        raise _not_found()
    return r


def _lock_item(session: Session, item_id: int) -> Item:
    item = session.exec(select(Item).where(Item.id == item_id).with_for_update()).first()
    if not item:
        raise _not_found("물품")
    return item


def _touch(r: Reservation) -> None:
    r.updated_at = now_utc()


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        if "pgm_reservation_no_overlap" in str(e.orig):
            raise RuleError(409, "같은 시간대에 이미 확정된 예약이 있습니다.") from e
        raise


def cancel_reservation(session: Session, actor: User, reservation_id: int, reason: str | None) -> Reservation:
    r = _lock_reservation(session, reservation_id)
    is_admin = actor.role == ROLE_ADMIN
    if r.user_id != actor.id and not is_admin:
        raise _not_found()  # 다른 사람 예약의 존재 여부를 알리지 않는다
    if r.status not in (R_PENDING, R_APPROVED):
        session.rollback()
        raise _bad_state(r, "취소")
    if is_admin and r.user_id != actor.id and not (reason and reason.strip()):
        session.rollback()
        raise RuleError(422, "관리자가 취소할 때는 사유를 입력해 주세요.")
    r.status = R_CANCELLED
    r.cancelled_at = now_utc()
    r.cancel_reason = (reason or "").strip() or None
    _touch(r)
    _commit(session)
    session.refresh(r)
    return r


# ---------------------------------------------------------------- 관리자: 승인 / 거절


def approve_reservation(session: Session, admin: User, reservation_id: int) -> Reservation:
    r = _lock_reservation(session, reservation_id)
    if r.status != R_PENDING:
        session.rollback()
        raise _bad_state(r, "승인")
    item = _lock_item(session, r.item_id)  # 같은 물품의 승인을 직렬화
    if item.status == ITEM_REPAIR:
        session.rollback()
        raise RuleError(409, "수리 중인 물품은 예약을 승인할 수 없습니다.")
    if item.status == ITEM_RETIRED:
        session.rollback()
        raise RuleError(409, "보관 종료된 물품은 예약을 승인할 수 없습니다.")
    if to_utc(r.end_at) <= now_utc():
        session.rollback()
        raise RuleError(409, "이미 종료 시각이 지난 신청은 승인할 수 없습니다.")
    clash = find_overlapping(session, r.item_id, r.start_at, r.end_at, exclude_id=r.id)
    if clash:
        c = clash[0]
        session.rollback()
        raise RuleError(
            409,
            f"이미 확정된 예약(#{c.id}, {fmt_seoul(c.start_at)} ~ {fmt_seoul(c.end_at)})과 겹쳐 승인할 수 없습니다.",
        )
    r.status = R_APPROVED
    r.decided_by = admin.id
    r.decided_at = now_utc()
    _touch(r)
    _commit(session)
    session.refresh(r)
    return r


def reject_reservation(session: Session, admin: User, reservation_id: int, reason: str) -> Reservation:
    reason = (reason or "").strip()
    if not reason:
        raise RuleError(422, "거절 사유를 입력해 주세요.")
    r = _lock_reservation(session, reservation_id)
    if r.status != R_PENDING:
        session.rollback()
        raise _bad_state(r, "거절")
    r.status = R_REJECTED
    r.reject_reason = reason[:300]
    r.decided_by = admin.id
    r.decided_at = now_utc()
    _touch(r)
    _commit(session)
    session.refresh(r)
    return r


# ---------------------------------------------------------------- 관리자: 인계(대여 시작)


def checkout_blockers(session: Session, r: Reservation, item: Item, now: datetime | None = None) -> list[str]:
    """대여 시작을 막는 사유 목록 (화면 경고에도 사용)."""
    now = now or now_utc()
    reasons: list[str] = []
    if item.status == ITEM_REPAIR:
        reasons.append("물품이 수리 중입니다.")
    if item.status == ITEM_RETIRED:
        reasons.append("보관 종료된 물품입니다.")
    for other in unreturned_rentals(session, item.id, exclude_id=r.id):
        reasons.append(
            f"이전 대여(#{other.id}, 반납 기한 {fmt_seoul(other.end_at)})가 아직 반납 완료되지 않았습니다."
        )
    if to_utc(r.end_at) <= now:
        reasons.append("예약 종료 시각이 이미 지났습니다.")
    elif to_utc(r.start_at) - timedelta(minutes=config.CHECKOUT_EARLY_MINUTES) > now:
        reasons.append(f"예약 시작 {config.CHECKOUT_EARLY_MINUTES}분 전부터 인계할 수 있습니다.")
    return reasons


def checkout_reservation(session: Session, admin: User, reservation_id: int) -> Reservation:
    r = _lock_reservation(session, reservation_id)
    if r.status != R_APPROVED:
        session.rollback()
        raise _bad_state(r, "대여 시작")
    item = _lock_item(session, r.item_id)
    blockers = checkout_blockers(session, r, item)
    if blockers:
        session.rollback()
        raise RuleError(409, "대여를 시작할 수 없습니다: " + " ".join(blockers))
    r.status = R_IN_USE
    r.checked_out_at = now_utc()
    r.checked_out_by = admin.id
    _touch(r)
    _commit(session)
    session.refresh(r)
    return r


# ---------------------------------------------------------------- 반납


def request_return(session: Session, user: User, reservation_id: int, note: str | None) -> Reservation:
    r = _lock_reservation(session, reservation_id)
    if r.user_id != user.id:
        session.rollback()
        raise _not_found()
    if r.status != R_IN_USE:
        session.rollback()
        raise _bad_state(r, "반납 요청")
    r.status = R_RETURN_REQUESTED
    r.return_requested_at = now_utc()
    r.return_request_note = (note or "").strip()[:300] or None
    _touch(r)
    _commit(session)
    session.refresh(r)
    return r


@dataclass
class ReturnResult:
    reservation: Reservation
    report: DamageReport | None
    affected: list[Reservation]


def complete_return(
    session: Session, admin: User, reservation_id: int, condition: str, note: str | None
) -> ReturnResult:
    if condition not in (COND_NORMAL, COND_NEEDS_REPAIR):
        raise RuleError(422, "반납 상태(정상/수리 필요)를 선택해 주세요.")
    note = (note or "").strip()[:300] or None
    r = _lock_reservation(session, reservation_id)
    if r.status == R_RETURNED:
        session.rollback()
        raise RuleError(409, "이미 반납 완료된 대여입니다.")
    if r.status not in UNRETURNED:
        session.rollback()
        raise _bad_state(r, "반납 완료 처리")
    now = now_utc()
    r.status = R_RETURNED
    r.returned_at = now
    r.returned_by = admin.id
    r.return_condition = condition
    r.return_note = note
    _touch(r)
    report = None
    affected: list[Reservation] = []
    if condition == COND_NEEDS_REPAIR:
        item = _lock_item(session, r.item_id)
        item.status = ITEM_REPAIR
        item.updated_at = now
        report = DamageReport(
            item_id=item.id,
            reporter_id=admin.id,
            reservation_id=r.id,
            description=f"반납 확인 시 수리 필요로 기록됨. {note or ''}".strip(),
            status=REPORT_IN_PROGRESS,
            handled_by=admin.id,
        )
        session.add(report)
    _commit(session)
    session.refresh(r)
    if report:
        session.refresh(report)
        affected = affected_reservations(session, r.item_id)
    return ReturnResult(r, report, affected)


# ---------------------------------------------------------------- 고장 신고


def create_report(
    session: Session, user: User, item_id: int, description: str, reservation_id: int | None
) -> DamageReport:
    description = (description or "").strip()
    if len(description) < 5:
        raise RuleError(422, "고장·파손 내용을 5자 이상 입력해 주세요.")
    item = session.get(Item, item_id)
    if not item:
        raise _not_found("물품")
    if reservation_id is not None:
        r = session.get(Reservation, reservation_id)
        if not r or (r.user_id != user.id and user.role != ROLE_ADMIN) or r.item_id != item_id:
            raise RuleError(422, "연결할 수 없는 예약입니다.")
    report = DamageReport(
        item_id=item_id, reporter_id=user.id, reservation_id=reservation_id, description=description[:2000]
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


@dataclass
class ItemStatusResult:
    item: Item
    affected: list[Reservation]


def set_item_status(session: Session, item_id: int, new_status: str) -> ItemStatusResult:
    item = _lock_item(session, item_id)
    item.status = new_status
    item.updated_at = now_utc()
    session.commit()
    session.refresh(item)
    affected = affected_reservations(session, item_id) if new_status != ITEM_NORMAL else []
    return ItemStatusResult(item, affected)


def update_report(
    session: Session, admin: User, report_id: int, status: str, admin_note: str | None, item_action: str
) -> tuple[DamageReport, list[Reservation]]:
    if status not in REPORT_STATUSES:
        raise RuleError(422, "처리 상태가 올바르지 않습니다.")
    if item_action not in ("none", "set_repair", "set_normal"):
        raise RuleError(422, "물품 상태 변경 값이 올바르지 않습니다.")
    report = session.exec(
        select(DamageReport).where(DamageReport.id == report_id).with_for_update()
    ).first()
    if not report:
        raise _not_found("고장 신고")
    if status == REPORT_RECEIVED and report.status != REPORT_RECEIVED:
        session.rollback()
        raise RuleError(409, "처리를 시작한 신고는 접수 상태로 되돌릴 수 없습니다.")
    report.status = status
    if admin_note is not None:
        report.admin_note = admin_note.strip()[:2000]
    report.handled_by = admin.id
    report.updated_at = now_utc()
    affected: list[Reservation] = []
    item = session.get(Item, report.item_id)
    if item_action == "set_repair":
        if item.status == ITEM_RETIRED:
            session.rollback()
            raise RuleError(409, "보관 종료된 물품의 상태는 바꿀 수 없습니다.")
        item.status = ITEM_REPAIR
        item.updated_at = now_utc()
    elif item_action == "set_normal":
        if item.status == ITEM_RETIRED:
            session.rollback()
            raise RuleError(409, "보관 종료된 물품의 상태는 바꿀 수 없습니다.")
        item.status = ITEM_NORMAL
        item.updated_at = now_utc()
    session.commit()
    session.refresh(report)
    if item_action == "set_repair":
        affected = affected_reservations(session, report.item_id)
    return report, affected
