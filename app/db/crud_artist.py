from datetime import datetime

from db.database import initialize_db
from db.crud_event import _EVENT_COLUMNS, _row_to_event
from log.logger import get_app_logger
from models.event import EventCreate

logger = get_app_logger(__name__)

_ZWNJ = "‌"

def normalize_name(name: str) -> str:
    """Normalize for identity matching: strip ZWNJ, collapse whitespace, casefold Latin."""
    return " ".join(name.replace(_ZWNJ, " ").split()).casefold()

_ARTIST_SELECT = ("SELECT id, name, normalized_name, name_en, ig_handle, bio, resolved, source_url, "
                  "attempts, summary, summary_event_count FROM artists")

_PERSIAN_RANGE = ("؀", "ۿ")

def _has_persian_chars(text: str) -> bool:
    lo, hi = _PERSIAN_RANGE
    return any(lo <= ch <= hi for ch in text)

def _row_to_dict(cur, row) -> dict:
    names = [d[0] for d in cur.description]
    return dict(zip(names, row))

def _query(sql: str, params: tuple) -> list[dict]:
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = [_row_to_dict(cur, r) for r in cur.fetchall()]
    except Exception:
        logger.error(f"Can't fetch artists for query: {sql} {params}",exc_info=True)
        rows = []
    finally:
        conn.close()
    return rows

def find_artist_by_normalized_name(normalized: str) -> int | None:
    normalized = normalize_name(normalized)  # accept raw input too
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, name_en, ig_handle, normalized_name FROM artists")
        rows = cur.fetchall()
    except Exception:
        logger.error("Can't fetch artists for normalized lookup",exc_info=True)
        rows = []
    finally:
        conn.close()
    for artist_id, name, name_en, ig_handle, normalized_name in rows:
        for candidate in (name, name_en, ig_handle, normalized_name):
            if candidate and normalize_name(candidate) == normalized:
                return artist_id
    return None


def get_artists_missing_normalized_name(limit: int) -> list[dict]:
    """Persian-script artists without an approved normalized_name and without a
    pending proposal. Persian filtering happens here (SQLite LIKE can't match
    unicode ranges); over-fetches to survive non-Persian rows."""
    rows = _query(
        """
        SELECT a.id, a.name FROM artists a
        WHERE a.normalized_name IS NULL
          AND NOT EXISTS (SELECT 1 FROM artist_name_proposals p
                          WHERE p.artist_id = a.id AND p.status = 'pending')
        ORDER BY a.id
        LIMIT ?
        """,
        (limit * 5,),
    )
    persian = [row for row in rows if _has_persian_chars(row["name"] or "")]
    return persian[:limit]


def set_normalized_name(artist_id: int, normalized_name: str) -> None:
    """Store the approved English spelling; the original name is never touched."""
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE artists SET normalized_name = ? WHERE id = ?",
                    (normalized_name, artist_id))
    except Exception:
        logger.error(f"Can't set normalized_name for artist id={artist_id}",exc_info=True)
        conn.rollback()
    else:
        conn.commit()
    finally:
        conn.close()

def create_artist(raw_name: str) -> int | None:
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO artists (name, created_at) VALUES (?, ?)",
            (raw_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        artist_id = cur.lastrowid
    except Exception:
        logger.error(f"Can't create artist with name={raw_name!r}",exc_info=True)
        conn.rollback()
        conn.close()
        return None
    else:
        conn.commit()
        conn.close()
        return artist_id

def link_event_artist(event_id: int, artist_id: int, artist_name_raw: str) -> None:
    """Link, keeping the first raw spelling seen for this (event, artist) pair."""
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO event_artists (event_id, artist_id, artist_name_raw) "
            "SELECT ?, ?, ? WHERE NOT EXISTS "
            "(SELECT 1 FROM event_artists WHERE event_id = ? AND artist_id = ?)",
            (event_id, artist_id, artist_name_raw, event_id, artist_id),
        )
    except Exception:
        logger.error(f"Can't link event {event_id} to artist {artist_id}",exc_info=True)
        conn.rollback()
    else:
        conn.commit()
    finally:
        conn.close()

def get_artist(artist_id: int) -> dict | None:
    rows = _query(f"{_ARTIST_SELECT} WHERE id = ?", (artist_id,))
    return rows[0] if rows else None

def get_event_artists(event_id: int) -> list[dict]:
    sql = f"""
        SELECT a.id, a.name, a.name_en, a.resolved, ea.artist_name_raw
        FROM event_artists ea JOIN artists a ON a.id = ea.artist_id
        WHERE ea.event_id = ? ORDER BY ea.id
    """
    return _query(sql, (event_id,))

def get_artist_ids_for_event(event_id: int) -> list[int]:
    return [row["id"] for row in get_event_artists(event_id)]

def search_artists(query: str, limit: int = 20) -> list[dict]:
    return _query(
        f"{_ARTIST_SELECT} WHERE name LIKE ? OR name_en LIKE ? OR normalized_name LIKE ? "
        "ORDER BY resolved DESC, id DESC LIMIT ?",
        (f"%{query}%", f"%{query}%", f"%{query}%", limit),
    )

def get_events_for_artist(artist_id: int) -> list[tuple[int, EventCreate]]:
    """Events linked to the artist via event_artists, plus raw performers LIKE fallback."""
    linked = _query(
        "SELECT e.id FROM events e JOIN event_artists ea ON ea.event_id = e.id "
        "WHERE ea.artist_id = ?",
        (artist_id,),
    )
    event_ids = {row["id"] for row in linked}
    artist = get_artist(artist_id)
    like_rows = _query(
        "SELECT id FROM events WHERE performers LIKE ?",
        (f"%{artist['name']}%",),
    ) if artist else []
    event_ids.update(row["id"] for row in like_rows)
    if not event_ids:
        return []
    cols = ", ".join(("id",) + _EVENT_COLUMNS)
    sql = f"SELECT {cols} FROM events WHERE id IN ({', '.join('?' for _ in event_ids)}) ORDER BY datetime"
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute(sql, tuple(event_ids))
        names = [d[0] for d in cur.description]
        rows = [dict(zip(names, r)) for r in cur.fetchall()]
    except Exception:
        logger.error(f"Can't fetch events for artist {artist_id}",exc_info=True)
        rows = []
    finally:
        conn.close()
    return [(row.pop("id"), _row_to_event(row)) for row in rows]

def get_related_artists(artist_id: int, limit: int = 12) -> list[dict]:
    """Artists who shared a stage with this one: linked co-performers first,
    plus names parsed from the artist's raw performers strings (covers legacy
    events without event_artists links). Deduped by artist id."""
    rows = _query(
        """
        SELECT DISTINCT a.id, a.name, a.resolved
        FROM event_artists me
        JOIN event_artists other
          ON other.event_id = me.event_id AND other.artist_id != me.artist_id
        JOIN artists a ON a.id = other.artist_id
        WHERE me.artist_id = ?
        ORDER BY a.name
        """,
        (artist_id,),
    )
    related = {row["id"]: row for row in rows}

    if get_artist(artist_id):
        by_normalized: dict[str, dict] = {}
        for row in _query(_ARTIST_SELECT, ()):  # small table; resolve in memory
            for candidate in (row["name"], row["normalized_name"], row["name_en"], row["ig_handle"]):
                if candidate:
                    by_normalized.setdefault(normalize_name(candidate), row)
        for _, event in get_events_for_artist(artist_id):
            for raw_name in (event.performers or "").split(","):
                match = by_normalized.get(normalize_name(raw_name))
                if match and match["id"] != artist_id:
                    related.setdefault(match["id"], match)
    return list(related.values())[:limit]

def update_artist_summary(artist_id: int, summary: str, event_count: int) -> None:
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE artists SET summary = ?, summary_event_count = ? WHERE id = ?",
            (summary, event_count, artist_id),
        )
    except Exception:
        logger.error(f"Can't update summary for artist id={artist_id}",exc_info=True)
        conn.rollback()
    else:
        conn.commit()
    finally:
        conn.close()

def get_artists_needing_summary(limit: int) -> list[dict]:
    """Artists whose linked-event count differs from the count their summary was
    built from (includes summary IS NULL, since that defaults to 0)."""
    return _query(
        """
        SELECT a.id, a.name, a.summary_event_count, COUNT(DISTINCT ea.event_id) AS linked_count
        FROM artists a JOIN event_artists ea ON ea.artist_id = a.id
        GROUP BY a.id
        HAVING linked_count != a.summary_event_count
        ORDER BY linked_count DESC
        LIMIT ?
        """,
        (limit,),
    )

def get_unresolved_artists(limit: int) -> list[dict]:
    return _query(
        f"{_ARTIST_SELECT} WHERE resolved = 0 AND attempts < ? ORDER BY id LIMIT ?",
        (3, limit),
    )

def update_artist_resolution(artist_id: int, name: str, name_en: str,
                             ig_handle: str, bio: str, source_url: str) -> None:
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE artists SET name = ?, name_en = ?, ig_handle = ?, bio = ?, "
            "source_url = ?, resolved = 1 WHERE id = ?",
            (name, name_en or None, ig_handle or None, bio or None, source_url, artist_id),
        )
    except Exception:
        logger.error(f"Can't update artist resolution for id={artist_id}",exc_info=True)
        conn.rollback()
    else:
        conn.commit()
    finally:
        conn.close()

def increment_artist_attempts(artist_id: int) -> None:
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE artists SET attempts = attempts + 1 WHERE id = ?", (artist_id,))
    except Exception:
        logger.error(f"Can't increment attempts for artist id={artist_id}",exc_info=True)
        conn.rollback()
    else:
        conn.commit()
    finally:
        conn.close()