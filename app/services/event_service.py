from db.crud_event import insert_event
from telegram.event_formatter import format_event_for_telegram
from telegram.bot import send_to_telegram
from models.event import EventCreate
from ig_scrapper.extractor import extract_caption
from open_ai.text_events import extract_event_from_ig_text

def post_manual_event_on_telegram(event:EventCreate) -> dict:
    """
    Posts a manually created event to Telegram and stores it in the database.
    
    Formats the event for Telegram, sends it via the Telegram bot, inserts the event into persistent storage, and returns the status and response from Telegram.
    
    Args:
        event: The event data to be posted.
    
    Returns:
        A dictionary containing the status of the Telegram send operation and the Telegram response.
    """
    telegram_msg = format_event_for_telegram(event)
    status,res = send_to_telegram(telegram_msg)
    insert_event(event)
    return {"status":status,"tg_response":res}

def post_ig_event_on_telegram(ig_link:str) -> dict:
    """
    Posts an event extracted from an Instagram link to Telegram.
    
    Extracts the caption from the given Instagram link, parses event information from the caption, and posts the event to Telegram. Returns the result of the Telegram posting operation.
    
    Args:
        ig_link: The URL of the Instagram post to extract event information from.
    
    Returns:
        A dictionary containing the status and response from the Telegram posting process.
    """
    post_content = extract_caption(ig_link)
    event = extract_event_from_ig_text(post_content)
    res = post_manual_event_on_telegram(event)
    # TODO: It's not clean
    return res


