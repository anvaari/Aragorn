"""Push notifications to bot users (sync, called from scheduler code)."""
from db import crud_bot
from log.logger import get_app_logger
from services.reminder_service import hours_before
from telegram.bot import send_text_to_chat
from telegram_bot.cards import format_reminder_ping
from utils.event_time import now_str

logger = get_app_logger(__name__)


def send_due_reminders() -> dict:
    """Send all due event reminders; called by the scheduler tick. Returns stats."""
    due = crud_bot.get_due_reminders(now_str())
    sent, failed = 0, 0
    for reminder in due:
        text = format_reminder_ping(
            reminder.get("event_title") or "",
            reminder.get("event_datetime"),
            reminder.get("event_location") or "",
            hours=hours_before(reminder.get("event_datetime"), reminder.get("remind_at")),
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