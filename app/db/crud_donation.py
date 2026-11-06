from datetime import datetime

from db.database import initialize_db
from log.logger import get_app_logger

logger = get_app_logger(__name__)

_ARTIST_COLUMNS = "id, chat_id, username, name, bio, ton_address, evm_address, status, revision"

def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _fetch(sql: str, params: tuple) -> list[dict]:
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        names = [d[0] for d in cur.description]
        rows = [dict(zip(names, r)) for r in cur.fetchall()]
    except Exception:
        logger.error(f"Can't fetch rows for query: {sql} {params}",exc_info=True)
        rows = []
    finally:
        conn.close()
    return rows

def _execute(sql: str, params: tuple) -> tuple[int, int | None]:
    """Run one write; returns (rowcount, lastrowid), (0, None) on failure."""
    conn = initialize_db()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        result = (cur.rowcount, cur.lastrowid)
    except Exception:
        logger.error(f"Can't execute query: {sql} {params}",exc_info=True)
        conn.rollback()
        return 0, None
    else:
        conn.commit()
        return result
    finally:
        conn.close()

def upsert_artist(chat_id: int, username: str | None, name: str, bio: str,
                  ton_address: str, evm_address: str) -> dict | None:
    """Create or edit the caller's artist profile; any edit sends it back to review."""
    _execute(
        "INSERT INTO artist_profiles (chat_id, username, name, bio, ton_address, evm_address, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET username = excluded.username, name = excluded.name, "
        "bio = excluded.bio, ton_address = excluded.ton_address, evm_address = excluded.evm_address, "
        "status = 'pending', revision = revision + 1",
        (chat_id, username, name, bio, ton_address, evm_address, _now_str()),
    )
    return get_artist_by_chat(chat_id)

def get_artist(artist_id: int) -> dict | None:
    rows = _fetch(f"SELECT {_ARTIST_COLUMNS} FROM artist_profiles WHERE id = ?", (artist_id,))
    return rows[0] if rows else None

def get_artist_by_chat(chat_id: int) -> dict | None:
    rows = _fetch(f"SELECT {_ARTIST_COLUMNS} FROM artist_profiles WHERE chat_id = ?", (chat_id,))
    return rows[0] if rows else None

def get_approved_artists() -> list[dict]:
    return _fetch(f"SELECT {_ARTIST_COLUMNS} FROM artist_profiles WHERE status = 'approved' "
                  "ORDER BY name", ())

def set_artist_status(artist_id: int, revision: int, status: str) -> bool:
    """Approve/reject exactly the revision the admin reviewed; False if it changed since."""
    rowcount, _ = _execute(
        "UPDATE artist_profiles SET status = ? WHERE id = ? AND revision = ? AND status = 'pending'",
        (status, artist_id, revision),
    )
    return rowcount > 0

def add_donation(artist_id: int, donor_chat_id: int, asset: str, amount: int | None = None,
                 tx_ref: str | None = None, status: str = "pending") -> int | None:
    """Insert a donation; None when tx_ref was already recorded (or on DB error)."""
    rowcount, donation_id = _execute(
        "INSERT OR IGNORE INTO donations (artist_id, donor_chat_id, asset, amount, tx_ref, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (artist_id, donor_chat_id, asset, amount, tx_ref, status, _now_str()),
    )
    return donation_id if rowcount > 0 else None

def get_donation(donation_id: int) -> dict | None:
    rows = _fetch("SELECT * FROM donations WHERE id = ?", (donation_id,))
    return rows[0] if rows else None

def get_pending_donations(asset: str, since: str) -> list[dict]:
    # shortcut: newest 100 only, so spammed intents can't make a sweep endless; add per-donor limits if abused
    return _fetch("SELECT * FROM donations WHERE asset = ? AND status = 'pending' AND created_at >= ? "
                  "ORDER BY id DESC LIMIT 100", (asset, since))

def confirm_donation(donation_id: int, amount: int, tx_ref: str) -> bool:
    """Mark a pending donation paid; False if another caller confirmed it first."""
    rowcount, _ = _execute(
        "UPDATE donations SET status = 'confirmed', amount = ?, tx_ref = ? WHERE id = ? AND status = 'pending'",
        (amount, tx_ref, donation_id),
    )
    return rowcount > 0

def get_artist_totals(artist_id: int) -> list[dict]:
    return _fetch("SELECT asset, SUM(amount) AS amount, COUNT(*) AS count FROM donations "
                  "WHERE artist_id = ? AND status = 'confirmed' GROUP BY asset ORDER BY asset",
                  (artist_id,))
