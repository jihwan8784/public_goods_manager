"""관리자 비밀 코드(ADMIN_ACCESS_CODE) 확인. 로그인과 최고 관리자 권한 변경에서 함께 쓴다.

틀린 횟수는 계정별로 세고, 정해진 횟수를 넘으면 잠깐 잠근다.
"""

import hmac
from datetime import timedelta

from fastapi.responses import JSONResponse
from sqlmodel import Session

from . import config
from .models import User
from .timeutil import now_utc


def check_admin_code(session: Session, user: User, code: str | None) -> JSONResponse | None:
    """통과하면 None, 막으면 돌려줄 응답."""
    now = now_utc()
    if user.admin_code_locked_until and user.admin_code_locked_until > now:
        mins = max(1, int((user.admin_code_locked_until - now).total_seconds() // 60) + 1)
        return JSONResponse(
            status_code=429,
            content={
                "detail": f"비밀 코드를 여러 번 틀려 잠겼습니다. 약 {mins}분 후 다시 시도해 주세요.",
                "code": "admin_code_locked",
            },
        )
    if not code:
        return JSONResponse(
            status_code=401,
            content={"detail": "관리자 비밀 코드를 입력해 주세요.", "code": "admin_code_required"},
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
            content={
                "detail": f"비밀 코드를 {config.ADMIN_CODE_MAX_FAILURES}번 틀려 {config.ADMIN_CODE_LOCK_MINUTES}분 동안 잠겼습니다.",
                "code": "admin_code_locked",
            },
        )
    session.commit()
    return JSONResponse(
        status_code=401,
        content={
            "detail": f"관리자 비밀 코드가 올바르지 않습니다. ({left}번 더 틀리면 잠깁니다)",
            "code": "admin_code_invalid",
        },
    )
