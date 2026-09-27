from db.crud_event import insert_event
from telegram.event_formatter import format_event_for_telegram
from telegram.bot import send_text_to_telegram,send_image_to_telegram
from models.event import EventCreate
from ig_scrapper.extractor import extract_caption_image
from open_ai.text_events import extract_event_from_ig_text
from open_ai.image_events import extract_text_from_image

def _extract_message_id(status: int, res: object) -> int | None:
    # Telegram returns 200 with ok:false on Markdown parse errors -> gate on both.
    if status != 200 or not isinstance(res, dict) or not res.get("ok"):
        return None
    message_id = (res.get("result") or {}).get("message_id")
    return message_id if isinstance(message_id, int) else None

def post_manual_event_on_telegram(event:EventCreate) -> dict:
    telegram_msg = format_event_for_telegram(event)
    status,res = send_text_to_telegram(telegram_msg)
    insert_event(event, _extract_message_id(status, res))
    return {"status":status,"tg_response":res}

def post_event_with_image_on_telegram(event:EventCreate,photo_url) -> dict:
    telegram_msg = format_event_for_telegram(event)
    status,res = send_image_to_telegram(telegram_msg,photo_url)
    insert_event(event, _extract_message_id(status, res))
    return {"status":status,"tg_response":res}

def post_ig_event_on_telegram(ig_link:str) -> dict:
    post_content,photo_url = extract_caption_image(ig_link)
    event = extract_event_from_ig_text(post_content)
    res = post_event_with_image_on_telegram(event,photo_url)
    # TODO: It's not clean
    return res

def post_image_event_on_telegram(event_detail_byte: bytes,event_image_bytes: bytes) -> dict:
    image_content = extract_text_from_image(event_detail_byte)
    event = extract_event_from_ig_text(image_content)
    res = post_event_with_image_on_telegram(event,event_image_bytes)
    return res


