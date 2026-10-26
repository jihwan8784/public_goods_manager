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
        _migrate_v2(conn)
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


# 1차 버전(단일 조직)으로 만든 DB를 여러 기관 구조로 올린다. 여러 번 실행해도 안전하다.
_V2_COLUMNS = [
    "ALTER TABLE pgm_user ADD COLUMN IF NOT EXISTS is_student BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE pgm_user ADD COLUMN IF NOT EXISTS school_id INTEGER REFERENCES pgm_org(id)",
    "ALTER TABLE pgm_user ADD COLUMN IF NOT EXISTS student_no VARCHAR(40)",
    "ALTER TABLE pgm_user ADD COLUMN IF NOT EXISTS student_status VARCHAR(10) NOT NULL DEFAULT 'none'",
    "ALTER TABLE pgm_user ADD COLUMN IF NOT EXISTS student_reject_reason VARCHAR(300)",
    "ALTER TABLE pgm_user ADD COLUMN IF NOT EXISTS student_reviewed_by INTEGER",
    "ALTER TABLE pgm_user ADD COLUMN IF NOT EXISTS student_reviewed_at TIMESTAMPTZ",
    "ALTER TABLE pgm_item ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES pgm_org(id)",
    "ALTER TABLE pgm_item ADD COLUMN IF NOT EXISTS access VARCHAR(10) NOT NULL DEFAULT 'public'",
    "CREATE INDEX IF NOT EXISTS ix_pgm_item_org_id ON pgm_item (org_id)",
    "CREATE INDEX IF NOT EXISTS ix_pgm_user_school_id ON pgm_user (school_id)",
    "CREATE INDEX IF NOT EXISTS ix_pgm_org_geo ON pgm_org (lat, lng)",
]


def _migrate_v3(conn) -> None:
    """이메일 인증·생년월일 추가. 기능 도입 전에 있던 계정은 인증된 것으로 본다(한 번만 실행)."""
    has_col = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'pgm_user' AND column_name = 'email_verified_at'"
        )
    ).first()
    if not has_col:
        conn.execute(text("ALTER TABLE pgm_user ADD COLUMN email_verified_at TIMESTAMPTZ DEFAULT now()"))
        conn.execute(text("ALTER TABLE pgm_user ALTER COLUMN email_verified_at DROP DEFAULT"))
    conn.execute(text("ALTER TABLE pgm_user ADD COLUMN IF NOT EXISTS birth_date DATE"))
    # 관리자 비밀 코드 잠금
    conn.execute(text("ALTER TABLE pgm_user ADD COLUMN IF NOT EXISTS admin_code_failures INTEGER NOT NULL DEFAULT 0"))
    conn.execute(text("ALTER TABLE pgm_user ADD COLUMN IF NOT EXISTS admin_code_locked_until TIMESTAMPTZ"))


def _migrate_v2(conn) -> None:
    for ddl in _V2_COLUMNS:
        conn.execute(text(ddl))
    _migrate_v3(conn)
    # 관리번호: 전체 고유 → 기관별 고유
    old_unique = conn.execute(
        text(
            "SELECT 1 FROM pg_indexes WHERE indexname = 'ix_pgm_item_asset_code' "
            "AND indexdef LIKE 'CREATE UNIQUE%'"
        )
    ).first()
    if old_unique:
        conn.execute(text("DROP INDEX ix_pgm_item_asset_code"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pgm_item_asset_code ON pgm_item (asset_code)"))
    has_uq = conn.execute(text("SELECT 1 FROM pg_constraint WHERE conname = 'uq_pgm_item_org_code'")).first()
    if not has_uq:
        conn.execute(text("ALTER TABLE pgm_item ADD CONSTRAINT uq_pgm_item_org_code UNIQUE (org_id, asset_code)"))
    # 기관이 없던 기존 물품은 '기본 기관'으로 옮긴다
    orphan = conn.execute(text("SELECT 1 FROM pgm_item WHERE org_id IS NULL LIMIT 1")).first()
    if orphan:
        org_id = conn.execute(
            text(
                "INSERT INTO pgm_org (kind, code, name, subtype, region, address, phone, geocode_status, source, active, created_at) "
                "VALUES ('other', 'default', '기본 기관', '', '', '', '', 'pending', 'manual', TRUE, now()) "
                "ON CONFLICT (kind, code) DO UPDATE SET name = pgm_org.name RETURNING id"
            )
        ).scalar_one()
        conn.execute(text("UPDATE pgm_item SET org_id = :o WHERE org_id IS NULL"), {"o": org_id})
        # 기존 관리자들은 기본 기관의 관리자도 맡는다
        conn.execute(
            text(
                "INSERT INTO pgm_org_admin (org_id, user_id, created_at) "
                "SELECT :o, id, now() FROM pgm_user WHERE role = 'admin' ON CONFLICT DO NOTHING"
            ),
            {"o": org_id},
        )
