from db.crud_event import insert_event
from telegram.event_formatter import format_event_for_telegram
from telegram.bot import send_to_telegram
from models.event import EventCreate

def post_event_on_telegram(event:EventCreate) -> dict:
    telegram_msg = format_event_for_telegram(event)
    status,res = send_to_telegram(telegram_msg)
    insert_event(event)
    return {"status":status,"tg_response":res}
