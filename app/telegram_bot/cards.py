"""Text cards for bot DMs (event card, new-event alert, reminder ping)."""
import re

from models.event import EventCreate
from telegram.event_formatter import LOC_PATTERN, _escape_md
from utils.event_time import fa_digits, format_jdatetime

UNKNOWN_TIME = "00:01"


def _location_part(location: str) -> str:
    if location and re.match(LOC_PATTERN, location):
        return f"📍 [لینک گوگل مپ](https://www.google.com/maps?q={location})"
    if location:
        return f"📍 {_escape_md(location)}"
    return ""


def format_event_card(event: EventCreate) -> str:
    """Compact full-detail card for DMs (tighter than the channel post format)."""
    if not event.date or event.time == UNKNOWN_TIME:
        when = "زمان نامشخص" + (f" — ساعت {fa_digits(event.time)}" if event.time and event.time != UNKNOWN_TIME else "")
    else:
        when = format_jdatetime(event.datetime)
    lines = [
        f"🎤 *{_escape_md(event.title or 'بدون عنوان')}*",
        "",
        f"🗓 {when}",
    ]
    if _location_part(event.location):
        lines.append(_location_part(event.location))
    if event.performers:
        lines.append(f"👥 هنرمندان: {_escape_md(event.performers)}")
    if event.ticket_info:
        lines.append(f"🎟 بلیط: {_escape_md(event.ticket_info)}")
    if event.description:
        lines.append(f"📝 {_escape_md(event.description)}")
    if event.instagram_link:
        lines.append(f"📸 [لینک اینستاگرام]({event.instagram_link})")
    if event.google_calendar_link:
        lines.append(f"📅 [افزودن به تقویم گوگل]({event.google_calendar_link})")
    return "\n".join(lines)


def format_reminder_ping(event_title: str, event_datetime: str | None,
                         location: str, hours: int) -> str:
    when = format_jdatetime(event_datetime) if event_datetime else "زمان نامشخص"
    lines = [
        f"⏰ *یادآوری: {fa_digits(hours)} ساعت مانده به رویداد*",
        "",
        f"🎤 *{_escape_md(event_title or 'رویداد')}*",
        f"🗓 {when}",
    ]
    if _location_part(location):
        lines.append(_location_part(location))
    lines.append("")
    lines.append("🎶 به‌زودی شروع می‌شود!")
    return "\n".join(lines)