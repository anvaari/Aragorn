from db.database import initialize_db
from models.event import EventCreate
from log.logger import get_app_logger
from datetime import datetime

logger = get_app_logger(__name__)

_EVENT_COLUMNS = ("title", "datetime", "description", "location",
                  "performers", "ticket_info", "instagram_link")

def insert_event(event:EventCreate) -> bool :
    event_dict = event.model_dump()
    del event_dict['date']
    del event_dict['time']
    event_dict['datetime'] = event.datetime
    event_dict['google_calendar_link'] = event.google_calendar_link
    event_dict['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    columns = ", ".join(event_dict.keys())
    placeholders = ", ".join("?" for _ in event_dict)
    insert_query = f"INSERT INTO events ({columns}) VALUES ({placeholders})"
    conn = initialize_db()

    try:
        cur = conn.cursor()
        cur.execute(insert_query, tuple(event_dict.values()))
    except Exception:
        logger.error(f"Can't Insert Query into database.Query:\n{insert_query}",exc_info=True)
        conn.rollback()
        conn.close()
        return False
    else:
        conn.commit()
        conn.close()
        return True

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

def get_events_by_jdate(jdate: str) -> list[EventCreate]:
    columns = ", ".join(_EVENT_COLUMNS)
    query = f"SELECT {columns} FROM events WHERE datetime LIKE ? ORDER BY datetime"
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute(query, (f"{jdate}%",))
        rows = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
    except Exception:
        logger.error(f"Can't fetch events for jdate={jdate}",exc_info=True)
        rows = []
    finally:
        conn.close()
    return [_row_to_event(r) for r in rows]
