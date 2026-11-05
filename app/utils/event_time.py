"""Datetime helpers for the bot: Shamsi/Gregorian parsing and reminder math.

events.datetime is stored as "YYYY-MM-DD HH:MM". New rows (GPT prompt) are
Shamsi; a few legacy rows are Gregorian. Year > 1500 is treated as Gregorian.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import jdatetime

from core.config import app_settings
from log.logger import get_app_logger

logger = get_app_logger(__name__)

_GREGORIAN_MIN_YEAR = 1500  # Shamsi years are 13xx-14xx; anything above is Gregorian

_JMONTHS_FA = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
               "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

def fa_digits(text: str) -> str:
    return str(text).translate(_FA_DIGITS)

def tehran_tz() -> ZoneInfo:
    return ZoneInfo(app_settings.digest_timezone)

def now_tehran() -> datetime:
    return datetime.now(tehran_tz())

def now_str() -> str:
    """Gregorian 'YYYY-MM-DD HH:MM' used for remind_at comparisons in SQL."""
    return now_tehran().strftime("%Y-%m-%d %H:%M")

def parse_event_datetime(value: str | None) -> datetime | None:
    """Parse an events.datetime value into a Tehran-aware datetime, or None."""
    if not value:
        return None
    try:
        date_part, _, time_part = value.strip().partition(" ")
        if not time_part:
            time_part = "00:01"
        year, month, day = (int(p) for p in date_part.split("-"))
        hour, minute = (int(p) for p in time_part.split(":"))
        if year > _GREGORIAN_MIN_YEAR:
            naive = datetime(year, month, day, hour, minute)
        else:
            gregorian = jdatetime.date(year, month, day).togregorian()
            naive = datetime(gregorian.year, gregorian.month, gregorian.day, hour, minute)
        return naive.replace(tzinfo=tehran_tz())
    except (ValueError, TypeError):
        logger.warning(f"Can't parse event datetime: {value!r}")
        return None

def event_remind_at(event_dt: datetime, hours: int) -> datetime:
    """Gregorian datetime to remind at, N hours before the event."""
    return event_dt - timedelta(hours=hours)

def jdate_for_offset(day_offset: int) -> tuple[str, str]:
    """Shamsi 'YYYY-MM-DD' for today + day_offset (digest_timezone), plus Persian weekday."""
    gregorian_target = now_tehran().date() + timedelta(days=day_offset)
    jd = jdatetime.date.fromgregorian(date=gregorian_target)
    jdate = f"{jd.year:04d}-{jd.month:02d}-{jd.day:02d}"
    weekday_fa = jdatetime.date.j_weekdays_fa[jd.isoweekday() - 1]
    return jdate, weekday_fa

def jday_short_label(day_offset: int) -> str:
    """Button label: امروز / فردا / 'شنبه ۳ مهر'."""
    if day_offset == 0:
        return "امروز"
    if day_offset == 1:
        return "فردا"
    jdate, weekday_fa = jdate_for_offset(day_offset)
    _, month, day = jdate.split("-")
    return f"{weekday_fa} {fa_digits(int(day))} {_JMONTHS_FA[int(month) - 1]}"

def jday_full_label(day_offset: int) -> str:
    """Header label: 'امروز — جمعه 1404-07-03'."""
    jdate, weekday_fa = jdate_for_offset(day_offset)
    if day_offset == 0:
        prefix = "امروز"
    elif day_offset == 1:
        prefix = "فردا"
    else:
        prefix = f"{fa_digits(day_offset)} روز دیگر"
    return f"{prefix} — {weekday_fa} {fa_digits(jdate)}"

def format_jdatetime(value: str | None) -> str:
    """Human display for an events.datetime string, Persian digits, weekday included."""
    dt = parse_event_datetime(value)
    if dt is None:
        return fa_digits(value or "")
    jd = jdatetime.date.fromgregorian(date=dt.date())
    weekday_fa = jdatetime.date.j_weekdays_fa[jd.isoweekday() - 1]
    jdate = f"{jd.year:04d}-{jd.month:02d}-{jd.day:02d}"
    return f"{weekday_fa} {fa_digits(jdate)} ساعت {fa_digits(dt.strftime('%H:%M'))}"