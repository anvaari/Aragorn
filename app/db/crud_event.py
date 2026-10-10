from db.database import initialize_db
from models.event import EventCreate
from log.logger import get_app_logger
from datetime import datetime

logger = get_app_logger(__name__)

_EVENT_COLUMNS = ("title", "datetime", "description", "location",
                  "performers", "ticket_info", "instagram_link")

def insert_event(event:EventCreate, tg_message_id: int | None = None) -> int | None:
    event_dict = event.model_dump()
    del event_dict['date']
    del event_dict['time']
    event_dict['datetime'] = event.datetime
    event_dict['google_calendar_link'] = event.google_calendar_link
    event_dict['tg_message_id'] = tg_message_id  # None -> NULL (same as pre-feature rows)
    event_dict['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Explicit id: legacy tables used "id int primary key" (not a rowid alias),
    # which never auto-assigns. MAX(id)+1 works for both old and new tables.
    columns = ", ".join(("id",) + tuple(event_dict.keys()))
    placeholders = ", ".join(("(SELECT COALESCE(MAX(id), 0) + 1 FROM events)",)
                             + tuple("?" for _ in event_dict))
    insert_query = f"INSERT INTO events ({columns}) VALUES ({placeholders})"
    conn = initialize_db()

    try:
        cur = conn.cursor()
        cur.execute(insert_query, tuple(event_dict.values()))
        rowid = cur.lastrowid
        row = cur.execute("SELECT id FROM events WHERE rowid = ?", (rowid,)).fetchone()
        event_id = row[0] if row else rowid
    except Exception:
        logger.error(f"Can't Insert Query into database.Query:\n{insert_query}",exc_info=True)
        conn.rollback()
        conn.close()
        return None
    else:
        conn.commit()
        conn.close()
        return event_id

def _row_to_event(row: dict) -> EventCreate:
    date_str, _, time_str = (row.get("datetime") or "").partition(" ")
    if not time_str:
        time_str = "00:01"
    return EventCreate(
        title=row.get("title") or "",
        date=date_str,
        time=time_str,
        description=row.get("description") or "",
        location=row.get("location") or "",
        performers=row.get("performers") or "",
        ticket_info=row.get("ticket_info") or "",
        instagram_link=row.get("instagram_link") or "",
    )

def _select_event_rows(where: str, params: tuple, *, with_id: bool = False,
                       with_tg_message_id: bool = False) -> list[dict]:
    columns = _EVENT_COLUMNS
    if with_id:
        columns += ("id",)
    if with_tg_message_id:
        columns += ("tg_message_id",)
    query = f"SELECT {', '.join(columns)} FROM events WHERE {where} ORDER BY datetime"
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        rows = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
    except Exception:
        logger.error(f"Can't fetch events (where={where})",exc_info=True)
        rows = []
    finally:
        conn.close()
    return rows

def get_events_by_jdate(jdate: str) -> list[EventCreate]:
    return [_row_to_event(r) for r in _select_event_rows("datetime LIKE ?", (f"{jdate}%",))]

def get_events_by_jdate_with_ids(jdate: str) -> list[tuple[int, EventCreate]]:
    rows = _select_event_rows("datetime LIKE ?", (f"{jdate}%",), with_id=True)
    return [(r.pop("id"), _row_to_event(r)) for r in rows]

def get_events_by_jdate_with_tg_message_ids(jdate: str) -> list[tuple[int | None, EventCreate]]:
    rows = _select_event_rows("datetime LIKE ?", (f"{jdate}%",), with_tg_message_id=True)
    return [(r.get("tg_message_id"), _row_to_event(r)) for r in rows]

def get_events_like_performer_with_ids(artist_name: str) -> list[tuple[int, EventCreate]]:
    rows = _select_event_rows("performers LIKE ?", (f"%{artist_name}%",), with_id=True)
    return [(r.pop("id"), _row_to_event(r)) for r in rows]

def get_event_by_id(event_id: int) -> EventCreate | None:
    rows = _select_event_rows("id = ?", (event_id,))
    return _row_to_event(rows[0]) if rows else None
