from datetime import datetime

from db.database import initialize_db
from log.logger import get_app_logger

logger = get_app_logger(__name__)

def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def upsert_bot_user(chat_id: int, username: str | None, first_name: str | None) -> None:
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO bot_users (chat_id, username, first_name, created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET username = excluded.username, first_name = excluded.first_name",
            (chat_id, username, first_name, _now_str()),
        )
    except Exception:
        logger.error(f"Can't upsert bot user chat_id={chat_id}",exc_info=True)
        conn.rollback()
    else:
        conn.commit()
    finally:
        conn.close()

def add_event_reminder(chat_id: int, event_id: int, remind_at: str) -> bool:
    """Insert a reminder row; ignored when the exact reminder already exists."""
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO event_reminders (chat_id, event_id, remind_at, created_at) "
            "VALUES (?, ?, ?, ?)",
            (chat_id, event_id, remind_at, _now_str()),
        )
        inserted = cur.rowcount > 0
    except Exception:
        logger.error(f"Can't add reminder chat_id={chat_id} event_id={event_id}",exc_info=True)
        conn.rollback()
        conn.close()
        return False
    else:
        conn.commit()
        conn.close()
        return inserted

_REMINDER_SELECT = (
    "SELECT r.id, r.chat_id, r.event_id, r.remind_at, r.sent, "
    "e.title AS event_title, e.datetime AS event_datetime, e.location AS event_location "
    "FROM event_reminders r LEFT JOIN events e ON e.id = r.event_id"
)

def _fetch_reminders(sql: str, params: tuple) -> list[dict]:
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        names = [d[0] for d in cur.description]
        rows = [dict(zip(names, r)) for r in cur.fetchall()]
    except Exception:
        logger.error(f"Can't fetch reminders for query: {sql} {params}",exc_info=True)
        rows = []
    finally:
        conn.close()
    return rows

def get_user_reminders(chat_id: int) -> list[dict]:
    sql = f"{_REMINDER_SELECT} WHERE r.chat_id = ? AND r.sent = 0 ORDER BY r.remind_at"
    return _fetch_reminders(sql, (chat_id,))

def get_due_reminders(now_str: str) -> list[dict]:
    sql = f"{_REMINDER_SELECT} WHERE r.sent = 0 AND r.remind_at <= ? ORDER BY r.remind_at"
    return _fetch_reminders(sql, (now_str,))

def mark_reminder_sent(reminder_id: int) -> None:
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE event_reminders SET sent = 1 WHERE id = ?", (reminder_id,))
    except Exception:
        logger.error(f"Can't mark reminder sent id={reminder_id}",exc_info=True)
        conn.rollback()
    else:
        conn.commit()
    finally:
        conn.close()

def delete_reminder(reminder_id: int, chat_id: int) -> bool:
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM event_reminders WHERE id = ? AND chat_id = ?",
                    (reminder_id, chat_id))
        deleted = cur.rowcount > 0
    except Exception:
        logger.error(f"Can't delete reminder id={reminder_id}",exc_info=True)
        conn.rollback()
        conn.close()
        return False
    else:
        conn.commit()
        conn.close()
        return deleted

def upsert_artist_follow(chat_id: int, artist_id: int,
                         notify_new: bool, notify_pre: bool, pre_hours: int = 2) -> None:
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO artist_follows (chat_id, artist_id, notify_new, notify_pre, pre_hours, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(chat_id, artist_id) DO UPDATE SET "
            "notify_new = excluded.notify_new, notify_pre = excluded.notify_pre, pre_hours = excluded.pre_hours",
            (chat_id, artist_id, int(notify_new), int(notify_pre), pre_hours, _now_str()),
        )
    except Exception:
        logger.error(f"Can't upsert follow chat_id={chat_id} artist_id={artist_id}",exc_info=True)
        conn.rollback()
    else:
        conn.commit()
    finally:
        conn.close()

_FOLLOW_SELECT = (
    "SELECT f.id, f.chat_id, f.artist_id, f.notify_new, f.notify_pre, f.pre_hours, "
    "a.name AS artist_name, a.name_en AS artist_name_en "
    "FROM artist_follows f JOIN artists a ON a.id = f.artist_id"
)

def _fetch_follows(sql: str, params: tuple) -> list[dict]:
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        names = [d[0] for d in cur.description]
        rows = [dict(zip(names, r)) for r in cur.fetchall()]
    except Exception:
        logger.error(f"Can't fetch follows for query: {sql} {params}",exc_info=True)
        rows = []
    finally:
        conn.close()
    return rows

def get_follow(chat_id: int, artist_id: int) -> dict | None:
    rows = _fetch_follows(f"{_FOLLOW_SELECT} WHERE f.chat_id = ? AND f.artist_id = ?",
                          (chat_id, artist_id))
    return rows[0] if rows else None

def get_user_follows(chat_id: int) -> list[dict]:
    return _fetch_follows(f"{_FOLLOW_SELECT} WHERE f.chat_id = ? ORDER BY f.id", (chat_id,))

def get_new_event_follows() -> list[dict]:
    return _fetch_follows(f"{_FOLLOW_SELECT} WHERE f.notify_new = 1 OR f.notify_pre = 1", ())

def delete_follow(follow_id: int, chat_id: int) -> bool:
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM artist_follows WHERE id = ? AND chat_id = ?", (follow_id, chat_id))
        deleted = cur.rowcount > 0
    except Exception:
        logger.error(f"Can't delete follow id={follow_id}",exc_info=True)
        conn.rollback()
        conn.close()
        return False
    else:
        conn.commit()
        conn.close()
        return deleted