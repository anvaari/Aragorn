from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import jdatetime

from core.config import app_settings
from db.crud_event import get_events_by_jdate
from log.logger import get_app_logger
from telegram.bot import send_text_to_telegram
from telegram.event_formatter import format_events_digest

logger = get_app_logger(__name__)

_DAY_LABELS = {0: "امروز", 1: "فردا"}

def _target_jdate(day_offset: int) -> tuple[str, str]:
    """Shamsi 'YYYY-MM-DD' for today (in digest_timezone) + day_offset, plus its Persian weekday."""
    tz = ZoneInfo(app_settings.digest_timezone)
    gregorian_target = datetime.now(tz).date() + timedelta(days=day_offset)
    jd = jdatetime.date.fromgregorian(date=gregorian_target)
    jdate = f"{jd.year:04d}-{jd.month:02d}-{jd.day:02d}"
    weekday_fa = jdatetime.date.j_weekdays_fa[jd.isoweekday() - 1]
    return jdate, weekday_fa

def send_events_digest(day_offset: int) -> dict:
    jdate, weekday_fa = _target_jdate(day_offset)
    label = _DAY_LABELS.get(day_offset, f"{day_offset} روز دیگر")
    day_label = f"{label} — {weekday_fa} {jdate}"

    events = get_events_by_jdate(jdate)
    if not events:
        logger.info(f"Digest {jdate} (day_offset={day_offset}): no events, staying silent")
        return {"sent": False, "reason": "no_events", "events": 0,
                "jdate": jdate, "day_offset": day_offset}

    digest_text = format_events_digest(events, day_label)
    status, res = send_text_to_telegram(digest_text)
    if status != 200:
        logger.error(f"Digest {jdate}: telegram send failed status={status} res={res}",exc_info=True)
    else:
        logger.info(f"Digest {jdate}: sent {len(events)} event(s)")
    return {"sent": status == 200, "status": status, "events": len(events),
            "jdate": jdate, "day_offset": day_offset}
