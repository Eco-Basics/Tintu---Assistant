from datetime import datetime, timezone
import zoneinfo
from app.config import TIMEZONE

# UTC is always available via datetime.timezone.utc — no tzdata package needed.
# For non-UTC zones, fall back to zoneinfo (requires tzdata on Windows).
_UTC_ALIASES = {"UTC", "utc", "Etc/UTC"}


def get_tz():
    if TIMEZONE in _UTC_ALIASES:
        return timezone.utc
    return zoneinfo.ZoneInfo(TIMEZONE)


def now() -> datetime:
    return datetime.now(tz=get_tz())


def today_str() -> str:
    return now().strftime("%Y-%m-%d")


def format_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


def parse_dt(s: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=get_tz())
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: {s!r}")
