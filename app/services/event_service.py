from db.crud_event import insert_event
from telegram.event_formatter import format_event_for_telegram
from telegram.bot import send_to_telegram
from models.event import EventCreate
from ig_scrapper.extractor import extract_caption
from open_ai.text_events import extract_event_from_ig_text

def post_manual_event_on_telegram(event:EventCreate) -> dict:
    telegram_msg = format_event_for_telegram(event)
    status,res = send_to_telegram(telegram_msg)
    insert_event(event)
    return {"status":status,"tg_response":res}

def post_ig_event_on_telegram(ig_link:str) -> dict:
    post_content = extract_caption(ig_link)
    event = extract_event_from_ig_text(post_content)
    res = post_manual_event_on_telegram(event)
    # TODO: It's not clean
    return res


