import threading

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from sqlmodel import Session, select

from . import config
from .db import engine, init_db
from .models import ROLE_ADMIN, User
from .people import router as people_router
from .routes import router
from .routes_orgs import router as orgs_router
from .security import hash_password
from .services import RuleError

FIELD_LABELS = {
    "email": "아이디",
    "password": "비밀번호",
    "name": "이름",
    "purpose": "사용 목적",
    "start_at": "시작 시각",
    "end_at": "종료 시각",
    "asset_code": "관리번호",
    "category": "카테고리",
    "description": "설명",
    "reason": "사유",
    "condition": "반납 상태",
    "school_id": "학교",
    "student_no": "학번",
    "org_id": "기관",
    "access": "이용 대상",
    "lat": "위도",
    "lng": "경도",
}


def bootstrap_admin() -> None:
    """BOOTSTRAP_ADMIN_* 가 설정되어 있고 관리자가 한 명도 없을 때만 최초 관리자 생성."""
    if not (config.BOOTSTRAP_ADMIN_EMAIL and config.BOOTSTRAP_ADMIN_PASSWORD):
        return
    with Session(engine) as s:
        if s.exec(select(User).where(User.role == ROLE_ADMIN)).first():
            return
        if s.exec(select(User).where(User.email == config.BOOTSTRAP_ADMIN_EMAIL)).first():
            return
        s.add(
            User(
                email=config.BOOTSTRAP_ADMIN_EMAIL,
                name=config.BOOTSTRAP_ADMIN_NAME,
                password_hash=hash_password(config.BOOTSTRAP_ADMIN_PASSWORD),
                role=ROLE_ADMIN,
            )
        )
        s.commit()


_startup_lock = threading.Lock()
_started = False


def ensure_startup() -> None:
    """첫 요청 때 한 번만 테이블 준비 + 최초 관리자 생성 (서버리스 환경 대응)."""
    global _started
    if _started:
        return
    with _startup_lock:
        if not _started:
            init_db()
            bootstrap_admin()
            _started = True


def create_app(run_startup: bool = True) -> FastAPI:
    app = FastAPI(title="public goods manage API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def no_store(request: Request, call_next):
        if run_startup:
            await run_in_threadpool(ensure_startup)
        response = await call_next(request)
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(RuleError)
    async def rule_error(_: Request, exc: RuleError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        fields = []
        for e in exc.errors():
            loc = [str(x) for x in e.get("loc", []) if x not in ("body", "query", "path")]
            if loc:
                fields.append(FIELD_LABELS.get(loc[-1], loc[-1]))
        label = ", ".join(dict.fromkeys(fields))
        msg = f"입력값을 확인해 주세요: {label}" if label else "입력값을 확인해 주세요."
        return JSONResponse(status_code=422, content={"detail": msg, "errors": jsonable(exc.errors())})

    @app.get("/")
    def health():
        return {"service": "public goods manage", "status": "ok"}

    app.include_router(router)
    app.include_router(people_router)
    app.include_router(orgs_router)
    return app


def jsonable(errors):
    out = []
    for e in errors:
        out.append({"loc": [str(x) for x in e.get("loc", [])], "msg": str(e.get("msg", ""))})
    return out
