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

# 공공데이터 / 지도
NEIS_API_KEY = os.getenv("NEIS_API_KEY", "")  # 교육청 학교 목록 (open.neis.go.kr)
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")  # 주소 → 좌표 변환 (서버 전용)
CRON_SECRET = os.getenv("CRON_SECRET", "")  # Vercel Cron 이 보내는 인증 값

# 메일: Gmail SMTP (기본). Gmail 주소 + 구글 계정의 '앱 비밀번호'(16자리)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").replace(" ", "")  # 앱 비밀번호는 띄어쓰기 없이
# 선택: SMTP 대신 Resend (내 도메인 인증 필요)
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
# 보내는 사람 표시. 비우면 "public goods manage <SMTP_USER>"
MAIL_FROM = os.getenv("MAIL_FROM", "")
# 메일 속 링크가 가리킬 사이트 주소 (웹 프로젝트 주소)
APP_BASE_URL = (os.getenv("APP_BASE_URL") or (ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else "http://localhost:3000")).rstrip("/")
VERIFY_TOKEN_HOURS = 24
RESET_TOKEN_MINUTES = 60
RESEND_COOLDOWN_SECONDS = 60  # 같은 사람에게 인증 메일을 다시 보내는 최소 간격

# 관리자(최고·기관 관리자) 로그인 비밀 코드. 비우면 코드 확인을 하지 않는다.
ADMIN_ACCESS_CODE = os.getenv("ADMIN_ACCESS_CODE", "").strip()
ADMIN_CODE_MAX_FAILURES = 5  # 연속으로 틀리면
ADMIN_CODE_LOCK_MINUTES = 15  # 이 시간 동안 관리자 로그인 잠금

# 학생 연령 확인
MIN_SIGNUP_AGE = 14  # 개인정보보호법: 만 14세 미만은 보호자 동의가 필요해 가입을 받지 않음
