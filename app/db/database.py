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
        id int primary key,
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
    try:
        cur = conn.cursor()
        cur.execute(events_ddl)
        existing_cols = {r[1] for r in cur.execute("PRAGMA table_info(events)").fetchall()}
        if "tg_message_id" not in existing_cols:
            try:
                cur.execute("ALTER TABLE events ADD COLUMN tg_message_id INTEGER")
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():  # a concurrent process may win the ALTER race
                    raise
    except Exception as e:
        logger.critical("Can't create event table on database",exc_info=True)
        raise e
    else:
        conn.commit()

