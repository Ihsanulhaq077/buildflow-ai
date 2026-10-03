from datetime import date, datetime, time, timedelta, timezone

from app.config import settings


def _tz() -> timezone:
    return timezone(timedelta(hours=settings.tz_offset_hours))


def local_today() -> date:
    return datetime.now(_tz()).date()


def day_bounds_utc(d: date) -> tuple[datetime, datetime]:
    """[start, end) of a local business day expressed in UTC."""
    start = datetime.combine(d, time.min, tzinfo=_tz()).astimezone(timezone.utc)
    return start, start + timedelta(days=1)
