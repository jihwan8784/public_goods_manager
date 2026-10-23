from datetime import datetime

from sqlalchemy import Column, DateTime, Index, LargeBinary, String, Text
from sqlmodel import Field, SQLModel

from .timeutil import now_utc

# 상태 값
ROLE_USER, ROLE_ADMIN = "user", "admin"
ROLES = (ROLE_USER, ROLE_ADMIN)

ITEM_NORMAL, ITEM_REPAIR, ITEM_RETIRED = "normal", "repair", "retired"
ITEM_STATUSES = (ITEM_NORMAL, ITEM_REPAIR, ITEM_RETIRED)

R_PENDING = "pending"                    # 승인 대기
R_APPROVED = "approved"                  # 예약 확정 (아직 인계 전)
R_REJECTED = "rejected"                  # 거절
R_CANCELLED = "cancelled"                # 취소
R_IN_USE = "in_use"                      # 대여 중 (실물 인계 완료)
R_RETURN_REQUESTED = "return_requested"  # 반납 요청 (실물 확인 전)
R_RETURNED = "returned"                  # 반납 완료
RESERVATION_STATUSES = (
    R_PENDING, R_APPROVED, R_REJECTED, R_CANCELLED, R_IN_USE, R_RETURN_REQUESTED, R_RETURNED,
)
# 기간을 점유하는 상태 (DB 배제 제약과 동일하게 유지)
OCCUPYING = (R_APPROVED, R_IN_USE, R_RETURN_REQUESTED)
# 실물이 아직 돌아오지 않은 상태
UNRETURNED = (R_IN_USE, R_RETURN_REQUESTED)

COND_NORMAL, COND_NEEDS_REPAIR = "normal", "needs_repair"

REPORT_RECEIVED = "received"        # 접수
REPORT_IN_PROGRESS = "in_progress"  # 수리 중
REPORT_RESOLVED = "resolved"        # 처리 완료
REPORT_DISMISSED = "dismissed"      # 이상 없음 종결
REPORT_STATUSES = (REPORT_RECEIVED, REPORT_IN_PROGRESS, REPORT_RESOLVED, REPORT_DISMISSED)
REPORT_OPEN = (REPORT_RECEIVED, REPORT_IN_PROGRESS)


class User(SQLModel, table=True):
    __tablename__ = "pgm_user"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(sa_column=Column(String(120), unique=True, nullable=False, index=True))
    name: str = Field(max_length=50)
    password_hash: str
    role: str = Field(default=ROLE_USER, max_length=10)
    created_at: datetime = Field(
        default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class Item(SQLModel, table=True):
    __tablename__ = "pgm_item"

    id: int | None = Field(default=None, primary_key=True)
    asset_code: str = Field(sa_column=Column(String(40), unique=True, nullable=False, index=True))
    name: str = Field(max_length=80, index=True)
    category: str = Field(max_length=40, index=True)
    description: str = Field(default="", sa_column=Column(Text, nullable=False, default=""))
    caution: str = Field(default="", sa_column=Column(Text, nullable=False, default=""))
    location: str = Field(default="", max_length=120)
    status: str = Field(default=ITEM_NORMAL, max_length=10, index=True)
    image_data: bytes | None = Field(default=None, sa_column=Column(LargeBinary, nullable=True))
    image_type: str | None = Field(default=None, max_length=40)
    image_version: int = Field(default=0)
    created_at: datetime = Field(
        default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class Reservation(SQLModel, table=True):
    __tablename__ = "pgm_reservation"
    __table_args__ = (Index("ix_pgm_reservation_item_time", "item_id", "start_at", "end_at"),)

    id: int | None = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="pgm_item.id", index=True)
    user_id: int = Field(foreign_key="pgm_user.id", index=True)
    start_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    end_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    purpose: str = Field(max_length=200)
    status: str = Field(default=R_PENDING, max_length=20, index=True)

    reject_reason: str | None = Field(default=None, max_length=300)
    cancel_reason: str | None = Field(default=None, max_length=300)
    decided_by: int | None = Field(default=None, foreign_key="pgm_user.id")
    decided_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    cancelled_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    checked_out_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    checked_out_by: int | None = Field(default=None, foreign_key="pgm_user.id")
    return_requested_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    return_request_note: str | None = Field(default=None, max_length=300)
    returned_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    returned_by: int | None = Field(default=None, foreign_key="pgm_user.id")
    return_condition: str | None = Field(default=None, max_length=20)
    return_note: str | None = Field(default=None, max_length=300)

    created_at: datetime = Field(
        default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class DamageReport(SQLModel, table=True):
    __tablename__ = "pgm_damage_report"

    id: int | None = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="pgm_item.id", index=True)
    reporter_id: int = Field(foreign_key="pgm_user.id", index=True)
    reservation_id: int | None = Field(default=None, foreign_key="pgm_reservation.id")
    description: str = Field(sa_column=Column(Text, nullable=False))
    status: str = Field(default=REPORT_RECEIVED, max_length=20, index=True)
    admin_note: str = Field(default="", sa_column=Column(Text, nullable=False, default=""))
    handled_by: int | None = Field(default=None, foreign_key="pgm_user.id")
    created_at: datetime = Field(
        default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
