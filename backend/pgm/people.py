"""회원가입·이메일 인증·비밀번호 재설정, 내 정보, 학생 인증 승인, 회원 관리."""

import hashlib
import secrets
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, Response
from sqlmodel import Session, col, select

from . import config, mailer
from .access import StaffUser, can_manage, managed_org_ids
from .models import (
    ORG_SCHOOL,
    R_APPROVED,
    R_CANCELLED,
    R_PENDING,
    ROLE_ADMIN,
    UNRETURNED,
    DamageReport,
    Reservation,
    STUDENT_APPROVED,
    STUDENT_NONE,
    STUDENT_PENDING,
    STUDENT_REJECTED,
    TOKEN_RESET,
    TOKEN_VERIFY,
    EmailToken,
    Organization,
    OrgAdmin,
    User,
)
from .schemas import (
    EmailIn,
    PasswordResetIn,
    ReasonIn,
    SignupIn,
    StudentRequestIn,
    TokenIn,
    UserCreateIn,
    UserUpdateIn,
    org_brief,
    orgs_by_id,
)
from .security import AdminUser, CurrentUser, SessionDep, create_token, hash_password
from .timeutil import SEOUL, now_utc

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
            "birth_date": user.birth_date,
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


# ================================================================ 연령 확인


def age_on(birth: date, today: date) -> int:
    """만 나이"""
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


# 학교급별로 다닐 수 있는 만 나이 범위 (조기 입학·유급 등을 고려해 넉넉하게)
SCHOOL_AGE_RANGE = {"초등학교": (5, 14), "중학교": (11, 18), "고등학교": (14, 22)}


def check_student_age(birth: date | None, school: Organization) -> None:
    if birth is None:
        raise HTTPException(422, "학생은 생년월일을 입력해 주세요.")
    today = now_utc().astimezone(SEOUL).date()
    if birth >= today:
        raise HTTPException(422, "생년월일을 다시 확인해 주세요.")
    age = age_on(birth, today)
    if age > 100:
        raise HTTPException(422, "생년월일을 다시 확인해 주세요.")
    if age < config.MIN_SIGNUP_AGE:
        raise HTTPException(
            422,
            f"만 {config.MIN_SIGNUP_AGE}세 미만은 보호자 동의가 필요해 아직 가입할 수 없습니다. 학교 선생님께 문의해 주세요.",
        )
    rng = SCHOOL_AGE_RANGE.get(school.subtype)
    if rng and not (rng[0] <= age <= rng[1]):
        raise HTTPException(422, f"만 {age}세는 {school.subtype}에 다니는 나이로 보기 어렵습니다. 학교와 생년월일을 확인해 주세요.")


# ================================================================ 이메일 인증 / 비밀번호 재설정


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_token(session: Session, user: User, purpose: str) -> str:
    raw = secrets.token_urlsafe(32)
    ttl = timedelta(hours=config.VERIFY_TOKEN_HOURS) if purpose == TOKEN_VERIFY else timedelta(minutes=config.RESET_TOKEN_MINUTES)
    # 같은 용도의 이전 링크는 더 이상 쓸 수 없게 한다
    for old in session.exec(
        select(EmailToken).where(EmailToken.user_id == user.id, EmailToken.purpose == purpose, EmailToken.used_at.is_(None))
    ).all():
        old.used_at = now_utc()
    session.add(EmailToken(user_id=user.id, purpose=purpose, token_hash=_hash(raw), expires_at=now_utc() + ttl))
    session.commit()
    return raw


def consume_token(session: Session, raw: str, purpose: str) -> User:
    tok = session.exec(
        select(EmailToken).where(EmailToken.token_hash == _hash(raw), EmailToken.purpose == purpose).with_for_update()
    ).first()
    if not tok or tok.used_at is not None:
        raise HTTPException(400, "이미 사용했거나 올바르지 않은 링크입니다. 메일을 다시 요청해 주세요.")
    if tok.expires_at <= now_utc():
        raise HTTPException(400, "링크 사용 기간이 지났습니다. 메일을 다시 요청해 주세요.")
    tok.used_at = now_utc()
    user = session.get(User, tok.user_id)
    if not user:
        raise HTTPException(400, "계정을 찾을 수 없습니다.")
    return user


def _send_verification(session: Session, user: User) -> dict:
    raw = issue_token(session, user, TOKEN_VERIFY)
    url = f"{config.APP_BASE_URL}/verify-email?token={raw}"
    try:
        sent = mailer.send(mailer.verification_mail(user.email, user.name, url))
    except mailer.MailError as e:
        return {"mail": "failed", "message": str(e)}
    out: dict = {"mail": "sent" if sent else "not_sent_dev"}
    if not sent:  # 개발 환경: 메일 대신 화면에서 링크를 바로 열 수 있게
        out["dev_link"] = url
    return out


def _recent_token(session: Session, user: User, purpose: str) -> bool:
    last = session.exec(
        select(EmailToken)
        .where(EmailToken.user_id == user.id, EmailToken.purpose == purpose)
        .order_by(col(EmailToken.created_at).desc())
    ).first()
    return bool(last and last.created_at > now_utc() - timedelta(seconds=config.RESEND_COOLDOWN_SECONDS))


# ================================================================ 회원가입 / 내 정보


@router.post("/auth/signup", status_code=201)
def signup(body: SignupIn, session: SessionDep):
    email = body.email.strip().lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(409, "이미 가입된 이메일입니다. 로그인해 주세요.")
    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password))
    if body.is_student:
        school = _school_or_422(session, body.school_id)
        student_no = (body.student_no or "").strip()
        if not student_no:
            raise HTTPException(422, "학번(또는 학년·반·번호)을 입력해 주세요.")
        check_student_age(body.birth_date, school)
        user.is_student = True
        user.school_id = school.id
        user.student_no = student_no
        user.birth_date = body.birth_date
        user.student_status = STUDENT_PENDING  # 학교 관리자가 확인해야 학교 물품 이용 가능
    session.add(user)
    session.commit()
    session.refresh(user)
    # 로그인은 이메일 인증 후에만 가능 (세션 쿠키를 주지 않는다)
    return {"email": user.email, **_send_verification(session, user)}


@router.post("/auth/verify-email")
def verify_email(body: TokenIn, response: Response, session: SessionDep):
    user = consume_token(session, body.token, TOKEN_VERIFY)
    if user.email_verified_at is None:
        user.email_verified_at = now_utc()
    session.commit()
    session.refresh(user)
    set_session_cookie(response, user)  # 인증 링크를 누르면 바로 로그인
    return {"user": me_out(session, user)}


@router.post("/auth/resend-verification")
def resend_verification(body: EmailIn, session: SessionDep):
    """가입 여부를 알려 주지 않도록 항상 같은 응답을 준다."""
    user = session.exec(select(User).where(User.email == body.email.strip().lower())).first()
    generic = {"message": "가입된 미인증 계정이면 인증 메일을 보냈습니다. 메일함(스팸함 포함)을 확인해 주세요."}
    if not user or user.email_verified_at is not None:
        return generic
    if _recent_token(session, user, TOKEN_VERIFY):
        raise HTTPException(429, f"잠시 후 다시 시도해 주세요. ({config.RESEND_COOLDOWN_SECONDS}초에 한 번 보낼 수 있습니다)")
    result = _send_verification(session, user)
    if result["mail"] == "failed":
        raise HTTPException(503, result["message"])
    return {**generic, **({"dev_link": result["dev_link"]} if "dev_link" in result else {})}


@router.post("/auth/password-reset/request")
def password_reset_request(body: EmailIn, session: SessionDep):
    user = session.exec(select(User).where(User.email == body.email.strip().lower())).first()
    generic = {"message": "가입된 이메일이면 비밀번호 재설정 메일을 보냈습니다. 메일함(스팸함 포함)을 확인해 주세요."}
    if not user:
        return generic
    if _recent_token(session, user, TOKEN_RESET):
        raise HTTPException(429, f"잠시 후 다시 시도해 주세요. ({config.RESEND_COOLDOWN_SECONDS}초에 한 번 보낼 수 있습니다)")
    raw = issue_token(session, user, TOKEN_RESET)
    url = f"{config.APP_BASE_URL}/reset-password?token={raw}"
    try:
        sent = mailer.send(mailer.reset_mail(user.email, user.name, url))
    except mailer.MailError as e:
        raise HTTPException(503, str(e))
    return {**generic, **({} if sent else {"dev_link": url})}


@router.post("/auth/password-reset/confirm")
def password_reset_confirm(body: PasswordResetIn, session: SessionDep):
    user = consume_token(session, body.token, TOKEN_RESET)
    user.password_hash = hash_password(body.password)
    if user.email_verified_at is None:
        user.email_verified_at = now_utc()  # 메일 링크를 연 것 자체가 주소 소유 확인
    session.commit()
    return {"message": "비밀번호를 바꿨습니다. 새 비밀번호로 로그인해 주세요."}


@router.get("/auth/me")
def me(user: CurrentUser, session: SessionDep):
    return {"user": me_out(session, user)}


@router.put("/me/student")
def request_student(body: StudentRequestIn, user: CurrentUser, session: SessionDep):
    """학생 인증 신청 (처음 신청, 거절 후 재신청, 전학 등 학교 변경). 다시 승인 대기 상태가 된다."""
    school = _school_or_422(session, body.school_id)
    birth = body.birth_date or user.birth_date
    check_student_age(birth, school)
    user.birth_date = birth
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
        "birth_date": u.birth_date,
        "age": age_on(u.birth_date, now_utc().astimezone(SEOUL).date()) if u.birth_date else None,
        "email_verified": u.email_verified_at is not None,
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
        "email_verified": u.email_verified_at is not None,
        "suspended": u.suspended_at is not None,
        "suspended_at": u.suspended_at,
        "suspend_reason": u.suspend_reason,
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
    org = None
    if body.org_id is not None:
        org = session.get(Organization, body.org_id)
        if not org:
            raise HTTPException(422, "관리할 기관을 다시 선택해 주세요.")
    u = User(
        email=email,
        name=body.name.strip(),
        password_hash=hash_password(body.password),
        email_verified_at=now_utc(),  # 관리자가 직접 만든 계정은 인증된 것으로 본다
    )
    session.add(u)
    session.flush()
    if org:
        session.add(OrgAdmin(org_id=org.id, user_id=u.id))
    session.commit()
    session.refresh(u)
    return {"user": me_out_light(u)}


@router.patch("/admin/users/{user_id}")
def admin_update_user(user_id: int, body: UserUpdateIn, admin: AdminUser, session: SessionDep):
    """비밀번호 변경·이메일 인증 처리. 최고 관리자 권한은 화면에서 주거나 뺄 수 없다.
    관리자 권한은 기관 단위로 준다 (POST/DELETE /admin/orgs/{org_id}/admins)."""
    u = session.get(User, user_id)
    if not u:
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")
    if body.password:
        u.password_hash = hash_password(body.password)
    if body.verify_email and u.email_verified_at is None:
        u.email_verified_at = now_utc()
    session.commit()
    session.refresh(u)
    return {"user": me_out_light(u)}



# ================================================================ 최고 관리자: 계정 중지·삭제


def _target_for_moderation(session: Session, admin: User, user_id: int) -> User:
    u = session.exec(select(User).where(User.id == user_id).with_for_update()).first()
    if not u:
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")
    if u.id == admin.id:
        raise HTTPException(409, "자기 자신의 계정은 중지하거나 삭제할 수 없습니다.")
    if u.role == ROLE_ADMIN:
        raise HTTPException(409, "최고 관리자 계정은 중지하거나 삭제할 수 없습니다.")
    return u


@router.post("/admin/users/{user_id}/suspend")
def suspend_user(user_id: int, body: ReasonIn, admin: AdminUser, session: SessionDep):
    """이용 중지: 로그인과 모든 이용이 바로 막힌다. 예약·대여 기록은 그대로 둔다."""
    u = _target_for_moderation(session, admin, user_id)
    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(422, "중지 사유를 입력해 주세요.")
    u.suspended_at = now_utc()
    u.suspend_reason = reason[:300]
    session.commit()
    session.refresh(u)
    return {"user": me_out_light(u)}


@router.post("/admin/users/{user_id}/unsuspend")
def unsuspend_user(user_id: int, admin: AdminUser, session: SessionDep):
    u = _target_for_moderation(session, admin, user_id)
    u.suspended_at = None
    u.suspend_reason = None
    session.commit()
    session.refresh(u)
    return {"user": me_out_light(u)}


@router.delete("/admin/users/{user_id}")
def delete_user(user_id: int, admin: AdminUser, session: SessionDep):
    """계정 삭제.
    - 빌려 간 물품이 아직 반납되지 않았으면 삭제할 수 없다.
    - 대기·확정 예약은 취소한다.
    - 예약·신고 기록이 없으면 완전히 지우고, 기록이 있으면 기록 보존을 위해 개인정보만 지운다(익명 처리)."""
    u = _target_for_moderation(session, admin, user_id)
    if session.exec(
        select(Reservation.id).where(Reservation.user_id == u.id, col(Reservation.status).in_(UNRETURNED))
    ).first():
        raise HTTPException(409, "아직 반납하지 않은 물품이 있어 삭제할 수 없습니다. 반납 완료 처리 후 삭제해 주세요.")
    now = now_utc()
    for r in session.exec(
        select(Reservation)
        .where(Reservation.user_id == u.id, col(Reservation.status).in_((R_PENDING, R_APPROVED)))
        .with_for_update()
    ).all():
        r.status = R_CANCELLED
        r.cancelled_at = now
        r.cancel_reason = "계정 삭제로 취소됨"
        r.updated_at = now
    for link in session.exec(select(OrgAdmin).where(OrgAdmin.user_id == u.id)).all():
        session.delete(link)
    for tok in session.exec(select(EmailToken).where(EmailToken.user_id == u.id)).all():
        session.delete(tok)
    session.flush()

    has_history = session.exec(select(Reservation.id).where(Reservation.user_id == u.id)).first() or session.exec(
        select(DamageReport.id).where(DamageReport.reporter_id == u.id)
    ).first()
    if has_history:
        u.email = f"deleted-{u.id}@deleted.invalid"
        u.name = "삭제된 회원"
        u.password_hash = hash_password(secrets.token_urlsafe(32))  # 아무도 로그인할 수 없게
        u.is_student = False
        u.school_id = None
        u.student_no = None
        u.student_status = STUDENT_NONE
        u.birth_date = None
        u.suspended_at = u.suspended_at or now
        u.suspend_reason = "삭제된 계정"
        mode = "anonymized"
    else:
        session.delete(u)
        mode = "deleted"
    session.commit()
    return {"ok": True, "mode": mode}
