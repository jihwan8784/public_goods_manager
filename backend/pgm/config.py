import os

from dotenv import load_dotenv

load_dotenv()


def _detect_env() -> str:
    explicit = os.getenv("APP_ENV")
    if explicit:
        return explicit.lower()
    # Vercel 배포(운영·미리보기)는 기본적으로 운영 환경으로 취급한다.
    if os.getenv("VERCEL_ENV"):
        return "production"
    return "development"


APP_ENV = _detect_env()
IS_PRODUCTION = APP_ENV == "production"

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/pgm")

_DEV_SECRET = "dev-only-insecure-secret-change-me"
SECRET_KEY = os.getenv("SECRET_KEY") or ""
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise RuntimeError("운영 환경에서는 SECRET_KEY 환경변수가 필요합니다.")
    SECRET_KEY = _DEV_SECRET

SESSION_COOKIE = "pgm_session"
SESSION_HOURS = int(os.getenv("SESSION_HOURS", "12"))
COOKIE_SECURE = IS_PRODUCTION or os.getenv("COOKIE_SECURE") == "1"

ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()
]

# 운영 환경 최초 관리자(선택). 관리자가 한 명도 없을 때만 생성된다.
BOOTSTRAP_ADMIN_EMAIL = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
BOOTSTRAP_ADMIN_PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
BOOTSTRAP_ADMIN_NAME = os.getenv("BOOTSTRAP_ADMIN_NAME", "관리자")

# 예약 규칙 상수
MAX_RESERVATION_DAYS = 14          # 한 번에 예약할 수 있는 최대 기간
MAX_ADVANCE_DAYS = 180             # 몇 일 뒤까지 예약 가능한지
CHECKOUT_EARLY_MINUTES = 30        # 예약 시작 몇 분 전부터 인계 가능한지
PAST_TOLERANCE_SECONDS = 60        # 요청 지연을 고려한 과거 시각 허용 오차
MAX_IMAGE_BYTES = 2 * 1024 * 1024
