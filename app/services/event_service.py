from db.crud_event import insert_event
from telegram.event_formatter import format_event_for_telegram
from telegram.bot import send_text_to_telegram,send_image_to_telegram
from models.event import EventCreate
from ig_scrapper.extractor import extract_caption_image
from open_ai.text_events import extract_event_from_ig_text
from open_ai.image_events import extract_text_from_image
from log.logger import get_app_logger

logger = get_app_logger(__name__)

def _post_store_pipeline(event_id: int | None, event:EventCreate, performer_names:list[str]) -> None:
    """After a successful insert: link artists and notify bot followers.

    Never breaks ingestion; both steps log their own failures. Lazy imports
    avoid a cycle (telegram_bot.notifier pulls in telegram + crud modules).
    """
    if not event_id:
        return
    try:
        from services.artist_service import link_event_artists
        link_event_artists(event_id, performer_names)
    except Exception:
        logger.error(f"Artist linking failed for event_id={event_id}",exc_info=True)
    try:
        from telegram_bot.notifier import notify_new_event
        notify_new_event(event_id, event)
    except Exception:
        logger.error(f"Follower notification failed for event_id={event_id}",exc_info=True)

def post_manual_event_on_telegram(event:EventCreate) -> dict:
    telegram_msg = format_event_for_telegram(event)
    status,res = send_text_to_telegram(telegram_msg)
    event_id = insert_event(event)
    _post_store_pipeline(event_id, event, event.performers.split(","))
    return {"status":status,"tg_response":res}

def post_event_with_image_on_telegram(event:EventCreate,photo_url,performer_names:list[str] | None = None) -> dict:
    telegram_msg = format_event_for_telegram(event)
    status,res = send_image_to_telegram(telegram_msg,photo_url)
    event_id = insert_event(event)
    _post_store_pipeline(event_id, event, performer_names or event.performers.split(","))
    return {"status":status,"tg_response":res}

def post_ig_event_on_telegram(ig_link:str) -> dict:
    post_content,photo_url = extract_caption_image(ig_link)
    event,performer_names = extract_event_from_ig_text(post_content)
    res = post_event_with_image_on_telegram(event,photo_url,performer_names)
    # TODO: It's not clean
    return res

def post_image_event_on_telegram(event_detail_byte: bytes,event_image_bytes: bytes) -> dict:
    image_content = extract_text_from_image(event_detail_byte)
    event,performer_names = extract_event_from_ig_text(image_content)
    res = post_event_with_image_on_telegram(event,event_image_bytes,performer_names)
    return res