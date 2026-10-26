from datetime import timedelta
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session

from . import config
from .db import get_session
from .models import ROLE_ADMIN, User
from .timeutil import now_utc

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_token(user_id: int) -> str:
    now = now_utc()
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=config.SESSION_HOURS)).timestamp()),
    }
    return jwt.encode(payload, config.SECRET_KEY, algorithm=ALGORITHM)


def read_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


SessionDep = Annotated[Session, Depends(get_session)]


def current_user(request: Request, session: SessionDep) -> User:
    token = request.cookies.get(config.SESSION_COOKIE)
    user_id = read_token(token) if token else None
    user = session.get(User, user_id) if user_id else None
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "로그인이 필요합니다.")
    if user.suspended_at is not None:
        # 이미 로그인해 있던 사람도 다음 요청부터 바로 막힌다
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "이용이 중지된 계정입니다.")
    return user


def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    # 권한은 매 요청마다 DB의 역할로 확인한다 (토큰에 역할을 담지 않음)
    if user.role != ROLE_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "관리자만 사용할 수 있는 기능입니다.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
AdminUser = Annotated[User, Depends(admin_user)]
