from collections.abc import Iterator

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from . import config


def normalize_url(url: str) -> str:
    # Vercel에서 psycopg2 드라이버를 명시적으로 사용 (기존 설정 유지)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def make_engine(url: str):
    return create_engine(normalize_url(url), pool_pre_ping=True, pool_size=5, max_overflow=5)


engine = make_engine(config.DATABASE_URL)

_OVERLAP_DDL = """
ALTER TABLE pgm_reservation
  ADD CONSTRAINT pgm_reservation_no_overlap
  EXCLUDE USING gist (
    item_id WITH =,
    tstzrange(start_at, end_at, '[)') WITH &&
  ) WHERE (status IN ('approved', 'in_use', 'return_requested'))
"""


def init_db(eng=None) -> None:
    """테이블과 제약조건을 만든다. 여러 번 실행해도 안전하다."""
    from . import models  # noqa: F401  (모델 등록)

    eng = eng or engine
    with eng.begin() as conn:
        # 서버리스에서 동시에 여러 인스턴스가 떠도 한 번에 하나만 실행
        conn.execute(text("SELECT pg_advisory_xact_lock(7316001)"))
        SQLModel.metadata.create_all(conn)
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
        exists = conn.execute(
            text("SELECT 1 FROM pg_constraint WHERE conname = 'pgm_reservation_no_overlap'")
        ).first()
        if not exists:
            conn.execute(text(_OVERLAP_DDL))
        exists = conn.execute(
            text("SELECT 1 FROM pg_constraint WHERE conname = 'pgm_reservation_time_order'")
        ).first()
        if not exists:
            conn.execute(
                text(
                    "ALTER TABLE pgm_reservation ADD CONSTRAINT pgm_reservation_time_order "
                    "CHECK (start_at < end_at)"
                )
            )


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
