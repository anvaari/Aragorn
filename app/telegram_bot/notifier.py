"""Push notifications to bot users (sync, called from service/scheduler code)."""
from db import crud_bot
from models.event import EventCreate
from log.logger import get_app_logger
from telegram.bot import send_text_to_chat
from telegram_bot.cards import format_new_event_alert, format_reminder_ping
from utils.event_time import event_remind_at, now_str, now_tehran, parse_event_datetime
from db.crud_artist import normalize_name

logger = get_app_logger(__name__)


def notify_new_event(event_id: int, event: EventCreate) -> None:
    """Fan out to followers of any linked artist; pre-create their pre-event reminders.

    Safe to call for events with no followers; never raises.
    """
    try:
        follows = crud_bot.get_new_event_follows()
        if not follows:
            return
        from db.crud_artist import get_artist_ids_for_event
        linked_ids = set(get_artist_ids_for_event(event_id))
        performers_normalized = normalize_name(event.performers)

        for follow in follows:
            matched = (follow["artist_id"] in linked_ids
                       or normalize_name(follow["artist_name"]) in performers_normalized)
            if not matched:
                continue
            if follow["notify_new"]:
                _send_alert(follow["chat_id"], event)
            if follow["notify_pre"]:
                _create_pre_reminder(follow["chat_id"], event_id, event, follow["pre_hours"] or 2)
    except Exception:
        logger.error(f"notify_new_event failed for event_id={event_id}",exc_info=True)


def _send_alert(chat_id: int, event: EventCreate) -> None:
    try:
        status, res = send_text_to_chat(chat_id, format_new_event_alert(event))
        if status != 200:
            logger.error(f"New-event alert failed chat_id={chat_id} status={status} res={res}")
    except Exception:
        logger.error(f"New-event alert failed chat_id={chat_id}",exc_info=True)


def _create_pre_reminder(chat_id: int, event_id: int, event: EventCreate, pre_hours: int) -> None:
    event_dt = parse_event_datetime(event.datetime)
    if event_dt is None:
        return
    remind_at = event_remind_at(event_dt, pre_hours)
    if remind_at <= now_tehran():
        return  # event (or reminder time) already past
    crud_bot.add_event_reminder(chat_id, event_id, remind_at.strftime("%Y-%m-%d %H:%M"))


def send_due_reminders() -> dict:
    """Send all due event reminders; called by the scheduler tick. Returns stats."""
    due = crud_bot.get_due_reminders(now_str())
    sent, failed = 0, 0
    for reminder in due:
        event_dt = parse_event_datetime(reminder.get("event_datetime"))
        remind_dt = parse_event_datetime(reminder.get("remind_at"))
        hours = 0
        if event_dt and remind_dt:
            hours = max(0, round((event_dt - remind_dt).total_seconds() / 3600))
        text = format_reminder_ping(
            reminder.get("event_title") or "",
            reminder.get("event_datetime"),
            reminder.get("event_location") or "",
            hours=hours,
        )
        try:
            status, res = send_text_to_chat(reminder["chat_id"], text)
        except Exception:
            logger.error(f"Reminder ping failed reminder_id={reminder['id']}",exc_info=True)
            failed += 1
            continue
        if status == 200:
            crud_bot.mark_reminder_sent(reminder["id"])
            sent += 1
        else:
            logger.error(f"Reminder ping failed reminder_id={reminder['id']} status={status} res={res}")
            failed += 1
    if due:
        logger.info(f"Reminder tick: sent={sent} failed={failed}")
    return {"due": len(due), "sent": sent, "failed": failed}