from db.database import initialize_db
from models.event import EventCreate
from log.logger import get_app_logger
from datetime import datetime

logger = get_app_logger(__name__)

def insert_event(event:EventCreate) -> bool :
    """
    Inserts a new event record into the database.
    
    Args:
    	event: An EventCreate model instance containing event details.
    
    Returns:
    	True if the event was successfully inserted; False otherwise.
    """
    event_dict = event.model_dump()
    del event_dict['date']
    del event_dict['time']
    event_dict['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    insert_query = f"""
    INSERT INTO events {str(tuple(event_dict.keys())).replace("'","")} VALUES {tuple(event_dict.values())}
    """
    conn = initialize_db()

    try:
        cur = conn.cursor()
        cur.execute(insert_query)
    except Exception as e:
        logger.error(f"Can't Insert Query into database.Query:\n{insert_query}",exc_info=True)
        conn.rollback
        return False
    else:
        conn.commit()
        conn.close()
        return True

