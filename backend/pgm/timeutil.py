from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_utc(dt: datetime) -> datetime:
    """시간대 정보가 없는 값은 Asia/Seoul 기준으로 보고 UTC로 변환한다."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=SEOUL)
    return dt.astimezone(timezone.utc)


def fmt_seoul(dt: datetime) -> str:
    return to_utc(dt).astimezone(SEOUL).strftime("%Y-%m-%d %H:%M")
