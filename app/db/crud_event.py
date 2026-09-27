from db.database import initialize_db
from models.event import EventCreate
from log.logger import get_app_logger
from datetime import datetime

logger = get_app_logger(__name__)

_EVENT_COLUMNS = ("title", "datetime", "description", "location",
                  "performers", "ticket_info", "instagram_link")

def insert_event(event:EventCreate) -> int | None:
    event_dict = event.model_dump()
    del event_dict['date']
    del event_dict['time']
    event_dict['datetime'] = event.datetime
    event_dict['google_calendar_link'] = event.google_calendar_link
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

def _fetch_events(where: str, params: tuple) -> list[tuple[int, EventCreate]]:
    columns = ", ".join(("id",) + _EVENT_COLUMNS)
    query = f"SELECT {columns} FROM events WHERE {where} ORDER BY datetime"
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        names = [d[0] for d in cur.description]
        rows = [dict(zip(names, r)) for r in cur.fetchall()]
    except Exception:
        logger.error(f"Can't fetch events for query: {where} {params}",exc_info=True)
        rows = []
    finally:
        conn.close()
    return [(row.pop("id"), _row_to_event(row)) for row in rows]

def get_events_by_jdate_with_ids(jdate: str) -> list[tuple[int, EventCreate]]:
    return _fetch_events("datetime LIKE ?", (f"{jdate}%",))

def get_events_by_jdate(jdate: str) -> list[EventCreate]:
    return [event for _, event in get_events_by_jdate_with_ids(jdate)]

def get_events_like_performer_with_ids(artist_name: str) -> list[tuple[int, EventCreate]]:
    return _fetch_events("performers LIKE ?", (f"%{artist_name}%",))

def get_event_by_id(event_id: int) -> EventCreate | None:
    events = _fetch_events("id = ?", (event_id,))
    return events[0][1] if events else None