"""기관별 권한과 대여 자격.

- 서비스 관리자(role=admin): 모든 기관 관리 + 기관·회원 관리
- 기관 관리자(pgm_org_admin): 자기 기관의 물품·예약·고장 신고·학생 승인만 관리
- 대여 자격: 이용 대상이 '누구나'인 물품은 로그인한 모든 사용자,
  '소속 전용' 물품은 그 학교에서 승인된 학생만
"""

from typing import Annotated

from fastapi import Depends, HTTPException
from sqlmodel import Session, col, select

from .models import (
    ACCESS_MEMBERS,
    ROLE_ADMIN,
    STUDENT_APPROVED,
    STUDENT_PENDING,
    STUDENT_REJECTED,
    Item,
    Organization,
    OrgAdmin,
    User,
)
from .security import CurrentUser, SessionDep


def managed_org_ids(session: Session, user: User) -> set[int] | None:
    """관리 가능한 기관 id. None 이면 전체(서비스 관리자)."""
    if user.role == ROLE_ADMIN:
        return None
    return set(session.exec(select(OrgAdmin.org_id).where(OrgAdmin.user_id == user.id)).all())


def can_manage(session: Session, user: User, org_id: int | None) -> bool:
    ids = managed_org_ids(session, user)
    return ids is None or (org_id is not None and org_id in ids)


def is_staff(session: Session, user: User) -> bool:
    ids = managed_org_ids(session, user)
    return ids is None or bool(ids)


def staff_user(user: CurrentUser, session: SessionDep) -> User:
    if not is_staff(session, user):
        raise HTTPException(403, "기관 관리자만 사용할 수 있는 기능입니다.")
    return user


StaffUser = Annotated[User, Depends(staff_user)]


def scope_filter(query, column, ids: set[int] | None):
    """관리 범위로 쿼리를 좁힌다."""
    if ids is None:
        return query
    return query.where(col(column).in_(ids or {-1}))


def eligibility(user: User, item: Item, org: Organization | None = None) -> tuple[bool, str | None]:
    """이 사용자가 이 물품을 예약할 수 있는가 (물품 상태와는 별개)."""
    if item.access != ACCESS_MEMBERS:
        return True, None
    org_name = org.name if org else "해당 학교"
    if not user.is_student or user.school_id != item.org_id:
        return False, f"{org_name} 학생만 빌릴 수 있는 물품입니다."
    if user.student_status == STUDENT_PENDING:
        return False, f"{org_name} 관리자의 학생 승인을 기다리는 중입니다."
    if user.student_status == STUDENT_REJECTED:
        return False, f"{org_name} 학생 인증이 거절되었습니다. 내 정보에서 다시 신청해 주세요."
    if user.student_status != STUDENT_APPROVED:
        return False, f"{org_name} 학생 인증이 필요합니다."
    return True, None
