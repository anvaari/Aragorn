import sqlite3
import os
from log.logger import get_app_logger
from core.config import app_settings

logger = get_app_logger(__name__)

def initialize_db() -> sqlite3.Connection :
    db_file_path = app_settings.database_file_path
    if not os.path.exists(db_file_path):
        logger.debug(f"DB with path={db_file_path} is not exists, going to create it")
    else:
        logger.debug(f"DB with path={db_file_path} already exsits, going to use it.")
    try:
        conn = sqlite3.connect(db_file_path)
        create_table(conn)
    except Exception as e:
        logger.error("Can't initialize database",exc_info=True)
        raise e
    else:
        return conn
        

def create_table(conn: sqlite3.Connection) -> None:
    events_ddl = """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY,
        title TEXT,
        datetime TEXT,
        description TEXT,
        location TEXT,
        performers TEXT,
        ticket_info TEXT,
        instagram_link TEXT,
        google_calendar_link TEXT,
        created_at TEXT,
        tg_message_id INTEGER
    )
    """
    bot_ddls = [
        """
        CREATE TABLE IF NOT EXISTS artists (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            normalized_name TEXT,
            name_en TEXT,
            ig_handle TEXT,
            bio TEXT,
            resolved INTEGER DEFAULT 0,
            source_url TEXT,
            attempts INTEGER DEFAULT 0,
            summary TEXT,
            summary_event_count INTEGER DEFAULT 0,
            created_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS event_artists (
            id INTEGER PRIMARY KEY,
            event_id INTEGER NOT NULL,
            artist_id INTEGER NOT NULL,
            artist_name_raw TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS artist_name_proposals (
            id INTEGER PRIMARY KEY,
            artist_id INTEGER NOT NULL,
            current_name TEXT,
            proposed_name TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            decided_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS bot_users (
            chat_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS event_reminders (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            event_id INTEGER NOT NULL,
            remind_at TEXT NOT NULL,
            sent INTEGER DEFAULT 0,
            created_at TEXT,
            UNIQUE(chat_id, event_id, remind_at)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS artist_follows (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            artist_id INTEGER NOT NULL,
            notify_new INTEGER DEFAULT 1,
            notify_pre INTEGER DEFAULT 0,
            pre_hours INTEGER DEFAULT 2,
            created_at TEXT,
            UNIQUE(chat_id, artist_id)
        )
        """,
    ]
    try:
        cur = conn.cursor()
        cur.execute(events_ddl)
        # Legacy tables declared "id int primary key" (not a rowid alias) left ids
        # NULL on every row; backfill from rowid so bot references work.
        cur.execute("UPDATE events SET id = rowid WHERE id IS NULL")
        existing_cols = {r[1] for r in cur.execute("PRAGMA table_info(events)").fetchall()}
        if "tg_message_id" not in existing_cols:
            try:
                cur.execute("ALTER TABLE events ADD COLUMN tg_message_id INTEGER")
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():  # a concurrent process may win the ALTER race
                    raise
        for bot_ddl in bot_ddls:
            cur.execute(bot_ddl)
        artist_cols = {r[1] for r in cur.execute("PRAGMA table_info(artists)").fetchall()}
        for col, col_ddl in (("normalized_name", "TEXT"),
                             ("summary", "TEXT"), ("summary_event_count", "INTEGER DEFAULT 0")):
            if col not in artist_cols:
                try:
                    cur.execute(f"ALTER TABLE artists ADD COLUMN {col} {col_ddl}")
                except sqlite3.OperationalError as e:
                    if "duplicate column" not in str(e).lower():  # a concurrent process may win the ALTER race
                        raise
    except Exception as e:
        logger.critical("Can't create tables on database",exc_info=True)
        raise e
    else:
        conn.commit()

