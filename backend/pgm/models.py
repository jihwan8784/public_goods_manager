from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, Float, Index, LargeBinary, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from .timeutil import now_utc

# 상태 값
ROLE_USER, ROLE_ADMIN = "user", "admin"
ROLES = (ROLE_USER, ROLE_ADMIN)

# 기관 종류
ORG_SCHOOL, ORG_CENTER, ORG_OTHER = "school", "community_center", "other"
ORG_KINDS = (ORG_SCHOOL, ORG_CENTER, ORG_OTHER)

# 학생 인증 상태
STUDENT_NONE, STUDENT_PENDING, STUDENT_APPROVED, STUDENT_REJECTED = "none", "pending", "approved", "rejected"

# 물품 이용 대상: 누구나 / 해당 기관 소속(승인된 학생)만
ACCESS_PUBLIC, ACCESS_MEMBERS = "public", "members"

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


class Organization(SQLModel, table=True):
    """공공기관(학교·주민센터 등). 공공데이터에서 동기화하거나 직접 등록한다."""

    __tablename__ = "pgm_org"
    __table_args__ = (UniqueConstraint("kind", "code", name="uq_pgm_org_kind_code"),)

    id: int | None = Field(default=None, primary_key=True)
    kind: str = Field(max_length=20, index=True)
    code: str = Field(max_length=60)  # 원본 데이터의 고유 코드 (NEIS 표준학교코드 등)
    name: str = Field(max_length=120, index=True)
    subtype: str = Field(default="", max_length=40)  # 초등학교/중학교/고등학교 등
    region: str = Field(default="", max_length=40)  # 시도
    address: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=40)
    lat: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    lng: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    geocode_status: str = Field(default="pending", max_length=10)  # pending | ok | failed | manual
    source: str = Field(default="manual", max_length=20)  # neis | csv | manual
    active: bool = Field(default=True, index=True)
    synced_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(
        default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class OrgAdmin(SQLModel, table=True):
    """기관 관리자 지정 (한 사용자가 여러 기관을 관리할 수 있음)."""

    __tablename__ = "pgm_org_admin"

    org_id: int = Field(foreign_key="pgm_org.id", primary_key=True)
    user_id: int = Field(foreign_key="pgm_user.id", primary_key=True, index=True)
    created_at: datetime = Field(
        default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class SyncRun(SQLModel, table=True):
    """기관 목록 동기화 기록."""

    __tablename__ = "pgm_sync_run"

    id: int | None = Field(default=None, primary_key=True)
    kind: str = Field(max_length=30)
    status: str = Field(default="running", max_length=10)  # running | ok | error
    message: str = Field(default="", sa_column=Column(Text, nullable=False, default=""))
    created: int = 0
    updated: int = 0
    deactivated: int = 0
    geocoded: int = 0
    started_at: datetime = Field(
        default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    finished_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class User(SQLModel, table=True):
    __tablename__ = "pgm_user"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(sa_column=Column(String(120), unique=True, nullable=False, index=True))
    name: str = Field(max_length=50)
    password_hash: str
    role: str = Field(default=ROLE_USER, max_length=10)  # admin = 서비스 전체 관리자
    is_student: bool = Field(default=False)
    school_id: int | None = Field(default=None, foreign_key="pgm_org.id", index=True)
    student_no: str | None = Field(default=None, max_length=40)
    student_status: str = Field(default=STUDENT_NONE, max_length=10, index=True)
    student_reject_reason: str | None = Field(default=None, max_length=300)
    student_reviewed_by: int | None = Field(default=None)
    student_reviewed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    birth_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    # 이메일 인증을 마친 시각. 비어 있으면 로그인할 수 없다.
    email_verified_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(
        default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


TOKEN_VERIFY, TOKEN_RESET = "verify", "reset"


class EmailToken(SQLModel, table=True):
    """이메일 인증·비밀번호 재설정 링크. 원문은 메일에만 있고 DB 에는 해시만 저장한다."""

    __tablename__ = "pgm_email_token"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="pgm_user.id", index=True)
    purpose: str = Field(max_length=10)
    token_hash: str = Field(sa_column=Column(String(64), unique=True, nullable=False, index=True))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    used_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(
        default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class Item(SQLModel, table=True):
    __tablename__ = "pgm_item"
    __table_args__ = (UniqueConstraint("org_id", "asset_code", name="uq_pgm_item_org_code"),)

    id: int | None = Field(default=None, primary_key=True)
    org_id: int | None = Field(default=None, foreign_key="pgm_org.id", index=True)
    access: str = Field(default=ACCESS_PUBLIC, max_length=10)
    asset_code: str = Field(sa_column=Column(String(40), nullable=False, index=True))
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
