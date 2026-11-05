from datetime import datetime

from db.database import initialize_db
from log.logger import get_app_logger

logger = get_app_logger(__name__)

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
        logger.error(f"Can't fetch proposals for query: {sql} {params}",exc_info=True)
        rows = []
    finally:
        conn.close()
    return rows

def create_proposal(artist_id: int, current_name: str, proposed_name: str) -> int | None:
    """Insert a pending proposal; None when one is already pending for the artist
    or the insert fails."""
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO artist_name_proposals (artist_id, current_name, proposed_name, status, created_at) "
            "SELECT ?, ?, ?, 'pending', ? WHERE NOT EXISTS "
            "(SELECT 1 FROM artist_name_proposals WHERE artist_id = ? AND status = 'pending')",
            (artist_id, current_name, proposed_name, _now(), artist_id),
        )
        if cur.rowcount == 0:
            conn.close()
            return None
        proposal_id = cur.lastrowid
    except Exception:
        logger.error(f"Can't create proposal for artist id={artist_id}",exc_info=True)
        conn.rollback()
        conn.close()
        return None
    else:
        conn.commit()
        conn.close()
        return proposal_id

def list_proposals(status: str | None = None, limit: int = 20, offset: int = 0) -> list[dict]:
    where, params = "", ()
    if status:
        where = "WHERE status = ?"
        params = (status,)
    return _query(
        f"SELECT * FROM artist_name_proposals {where} ORDER BY id LIMIT ? OFFSET ?",
        params + (limit, offset),
    )

def get_pending_proposals(limit: int, offset: int = 0) -> list[dict]:
    return list_proposals(status="pending", limit=limit, offset=offset)

def count_pending() -> int:
    rows = _query("SELECT COUNT(*) AS n FROM artist_name_proposals WHERE status = 'pending'", ())
    return rows[0]["n"] if rows else 0

def get_pending_ids() -> list[int]:
    return [row["id"] for row in _query(
        "SELECT id FROM artist_name_proposals WHERE status = 'pending' ORDER BY id", ())]

def get_proposal(proposal_id: int) -> dict | None:
    rows = _query("SELECT * FROM artist_name_proposals WHERE id = ?", (proposal_id,))
    return rows[0] if rows else None

def set_proposal_status(proposal_id: int, status: str) -> None:
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE artist_name_proposals SET status = ?, decided_at = ? WHERE id = ?",
            (status, _now(), proposal_id),
        )
    except Exception:
        logger.error(f"Can't set proposal status for id={proposal_id}",exc_info=True)
        conn.rollback()
    else:
        conn.commit()
    finally:
        conn.close()

def approve_proposal(proposal_id: int) -> None:
    """Approve the proposal and write the artist's normalized_name (one commit)."""
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE artist_name_proposals SET status = 'approved', decided_at = ? WHERE id = ?",
            (_now(), proposal_id),
        )
        cur.execute(
            "UPDATE artists SET normalized_name = "
            "(SELECT proposed_name FROM artist_name_proposals WHERE id = ?) WHERE id = "
            "(SELECT artist_id FROM artist_name_proposals WHERE id = ?)",
            (proposal_id, proposal_id),
        )
    except Exception:
        logger.error(f"Can't approve proposal id={proposal_id}",exc_info=True)
        conn.rollback()
    else:
        conn.commit()
    finally:
        conn.close()
