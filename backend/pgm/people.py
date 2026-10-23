"""회원가입, 내 정보, 학생 인증 승인, 회원 관리."""

from fastapi import APIRouter, HTTPException, Query, Response
from sqlmodel import Session, col, select

from . import config
from .access import StaffUser, can_manage, managed_org_ids
from .models import (
    ORG_SCHOOL,
    STUDENT_APPROVED,
    STUDENT_NONE,
    STUDENT_PENDING,
    STUDENT_REJECTED,
    Organization,
    OrgAdmin,
    User,
)
from .schemas import ReasonIn, SignupIn, StudentRequestIn, UserCreateIn, UserUpdateIn, org_brief, orgs_by_id
from .security import AdminUser, CurrentUser, SessionDep, create_token, hash_password
from .timeutil import now_utc

router = APIRouter()

STUDENT_LABEL = {
    STUDENT_NONE: "해당 없음",
    STUDENT_PENDING: "승인 대기",
    STUDENT_APPROVED: "승인됨",
    STUDENT_REJECTED: "거절됨",
}


def me_out(session: Session, user: User) -> dict:
    ids = managed_org_ids(session, user)
    managed = []
    if ids:
        managed = [org_brief(o) for o in orgs_by_id(session, ids).values()]
    school = session.get(Organization, user.school_id) if user.school_id else None
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "is_staff": ids is None or bool(ids),
        "managed_orgs": sorted(managed, key=lambda o: o["name"]),
        "student": {
            "is_student": user.is_student,
            "school": org_brief(school),
            "student_no": user.student_no,
            "status": user.student_status,
            "status_label": STUDENT_LABEL.get(user.student_status, user.student_status),
            "reject_reason": user.student_reject_reason,
        },
    }


def set_session_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        config.SESSION_COOKIE,
        create_token(user.id),
        max_age=config.SESSION_HOURS * 3600,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def _school_or_422(session: Session, school_id: int | None) -> Organization:
    school = session.get(Organization, school_id) if school_id else None
    if not school or school.kind != ORG_SCHOOL or not school.active:
        raise HTTPException(422, "다니는 학교를 목록에서 선택해 주세요.")
    return school


# ================================================================ 회원가입 / 내 정보


@router.post("/auth/signup", status_code=201)
def signup(body: SignupIn, response: Response, session: SessionDep):
    email = body.email.strip().lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(409, "이미 가입된 이메일입니다. 로그인해 주세요.")
    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password))
    if body.is_student:
        school = _school_or_422(session, body.school_id)
        student_no = (body.student_no or "").strip()
        if not student_no:
            raise HTTPException(422, "학번(또는 학년·반·번호)을 입력해 주세요.")
        user.is_student = True
        user.school_id = school.id
        user.student_no = student_no
        user.student_status = STUDENT_PENDING  # 학교 관리자가 확인해야 학교 물품 이용 가능
    session.add(user)
    session.commit()
    session.refresh(user)
    set_session_cookie(response, user)
    return {"user": me_out(session, user)}


@router.get("/auth/me")
def me(user: CurrentUser, session: SessionDep):
    return {"user": me_out(session, user)}


@router.put("/me/student")
def request_student(body: StudentRequestIn, user: CurrentUser, session: SessionDep):
    """학생 인증 신청 (처음 신청, 거절 후 재신청, 전학 등 학교 변경). 다시 승인 대기 상태가 된다."""
    school = _school_or_422(session, body.school_id)
    user.is_student = True
    user.school_id = school.id
    user.student_no = body.student_no.strip()
    user.student_status = STUDENT_PENDING
    user.student_reject_reason = None
    user.student_reviewed_by = None
    user.student_reviewed_at = None
    session.commit()
    session.refresh(user)
    return {"user": me_out(session, user)}


@router.delete("/me/student")
def cancel_student(user: CurrentUser, session: SessionDep):
    user.is_student = False
    user.school_id = None
    user.student_no = None
    user.student_status = STUDENT_NONE
    user.student_reject_reason = None
    session.commit()
    session.refresh(user)
    return {"user": me_out(session, user)}


# ================================================================ 학교 관리자: 학생 승인


def _student_row(u: User, school: Organization | None) -> dict:
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "student_no": u.student_no,
        "status": u.student_status,
        "status_label": STUDENT_LABEL.get(u.student_status, u.student_status),
        "reject_reason": u.student_reject_reason,
        "school": org_brief(school),
        "created_at": u.created_at,
        "reviewed_at": u.student_reviewed_at,
    }


@router.get("/admin/students")
def admin_students(
    staff: StaffUser,
    session: SessionDep,
    status: str = Query(default="pending", pattern="^(pending|approved|rejected|all)$"),
):
    ids = managed_org_ids(session, staff)
    q = select(User).where(User.is_student == True)  # noqa: E712
    if ids is not None:
        q = q.where(col(User.school_id).in_(ids or {-1}))
    if status != "all":
        q = q.where(User.student_status == status)
    rows = list(session.exec(q.order_by(User.created_at).limit(500)).all())
    schools = orgs_by_id(session, (u.school_id for u in rows))
    return {"students": [_student_row(u, schools.get(u.school_id)) for u in rows]}


def _review(session: Session, staff: User, user_id: int, status: str, reason: str | None) -> dict:
    u = session.exec(select(User).where(User.id == user_id).with_for_update()).first()
    if not u or not u.is_student or not can_manage(session, staff, u.school_id):
        raise HTTPException(404, "학생을 찾을 수 없습니다.")
    if status == STUDENT_REJECTED and not (reason and reason.strip()):
        raise HTTPException(422, "거절 사유를 입력해 주세요.")
    u.student_status = status
    u.student_reject_reason = reason.strip()[:300] if status == STUDENT_REJECTED and reason else None
    u.student_reviewed_by = staff.id
    u.student_reviewed_at = now_utc()
    session.commit()
    session.refresh(u)
    return {"student": _student_row(u, session.get(Organization, u.school_id))}


@router.post("/admin/students/{user_id}/approve")
def approve_student(user_id: int, staff: StaffUser, session: SessionDep):
    return _review(session, staff, user_id, STUDENT_APPROVED, None)


@router.post("/admin/students/{user_id}/reject")
def reject_student(user_id: int, body: ReasonIn, staff: StaffUser, session: SessionDep):
    return _review(session, staff, user_id, STUDENT_REJECTED, body.reason)


# ================================================================ 서비스 관리자: 회원


def _user_admin_row(session: Session, u: User, admin_map: dict[int, list[dict]]) -> dict:
    return {**me_out_light(u), "managed_orgs": admin_map.get(u.id, [])}


def me_out_light(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "role": u.role,
        "is_student": u.is_student,
        "student_status": u.student_status,
        "school_id": u.school_id,
    }


@router.get("/admin/users")
def admin_users(admin: AdminUser, session: SessionDep, q: str | None = Query(default=None, max_length=80)):
    query = select(User)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.where(col(User.name).ilike(like) | col(User.email).ilike(like))
    users = list(session.exec(query.order_by(User.role, User.name).limit(300)).all())
    links = session.exec(select(OrgAdmin)).all()
    orgs = orgs_by_id(session, {link.org_id for link in links})
    admin_map: dict[int, list[dict]] = {}
    for link in links:
        admin_map.setdefault(link.user_id, []).append(org_brief(orgs.get(link.org_id)))
    schools = orgs_by_id(session, (u.school_id for u in users))
    out = []
    for u in users:
        row = _user_admin_row(session, u, admin_map)
        row["school"] = org_brief(schools.get(u.school_id))
        out.append(row)
    return {"users": out}


@router.post("/admin/users", status_code=201)
def admin_create_user(body: UserCreateIn, admin: AdminUser, session: SessionDep):
    email = body.email.strip().lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(409, "이미 등록된 아이디(이메일)입니다.")
    u = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password), role=body.role)
    session.add(u)
    session.commit()
    session.refresh(u)
    return {"user": me_out_light(u)}


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
    return {"user": me_out_light(u)}

