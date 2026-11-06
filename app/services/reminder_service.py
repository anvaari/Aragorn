"""Event reminders, shared by the bot (inline buttons) and the Mini App."""
from db import crud_bot
from db.crud_event import get_event_by_id
from utils.event_time import event_remind_at, now_tehran, parse_event_datetime

REMINDER_HOURS = (2, 24)  # hours=0 ("both") creates both


def set_event_reminders(chat_id: int, event_id: int, hours: int) -> int:
    """Remind `hours` before the event (0 = both); returns how many reminders are new.

    Raises ValueError with a user-facing Persian message when no reminder is possible.
    """
    event = get_event_by_id(event_id)
    if not event:
        raise ValueError("🤔 رویداد مورد نظر پیدا نشد.")
    event_dt = parse_event_datetime(event.datetime)
    if event_dt is None:
        raise ValueError("😕 زمان این رویداد مشخص نیست و یادآوری ممکن نیست.")
    if event_dt <= now_tehran():
        raise ValueError("🕰 این رویداد گذشته یا در حال برگزاری است.")
    created = 0
    for hours_before_event in (REMINDER_HOURS if hours == 0 else (hours,)):
        remind_dt = event_remind_at(event_dt, hours_before_event)
        if remind_dt > now_tehran() and crud_bot.add_event_reminder(
                chat_id, event_id, remind_at=remind_dt.strftime("%Y-%m-%d %H:%M")):
            created += 1
    return created


def hours_before(event_datetime: str | None, remind_at: str | None) -> int:
    """How many hours before the event a reminder row fires (0 when unknown)."""
    event_dt, remind_dt = parse_event_datetime(event_datetime), parse_event_datetime(remind_at)
    if not (event_dt and remind_dt):
        return 0
    return max(0, round((event_dt - remind_dt).total_seconds() / 3600))
