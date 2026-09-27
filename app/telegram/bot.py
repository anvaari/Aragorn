import requests
from core.config import app_settings
from log.logger import get_app_logger

logger = get_app_logger(__name__)

def _proxies() -> dict:
    proxy = app_settings.tg_gpt_ig_proxy
    # TODO: Better check for proxy
    if 'http' in proxy :
        return {'http':proxy,'https':proxy}
    return {}

def send_text_to_chat(chat_id:str|int, text:str, reply_markup:str|None = None):
    """Send a Markdown message to an arbitrary chat (bot DMs to followers)."""
    token = app_settings.telegram_bot_token
    proxies = _proxies()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup is not None:
        data["reply_markup"] = reply_markup
    res = requests.post(
        url,
        data=data,
        proxies=proxies
    )
    return res.status_code,res.json()

def send_text_to_telegram(text):
    return send_text_to_chat(app_settings.telegram_chat_id, text)

def send_image_to_telegram(text:str,photo:str|bytes):
    token = app_settings.telegram_bot_token
    chat_id = app_settings.telegram_chat_id
    proxies = _proxies()
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    data = {
        "chat_id": chat_id, 
        "photo": photo,
        "caption": text,
        "parse_mode": "Markdown"
    }
    if isinstance(photo , str):
        res = requests.post(
            url, 
            data=data,
            proxies=proxies
        )
    elif isinstance(photo , bytes):
        del data['photo']
        files = {"photo": ("image.png", photo, "image/png")}
        res = requests.post(
            url,
            data=data,
            proxies=proxies,
            files=files
        )
    logger.info(f"PHOTO is {type(photo)}")
    return res.status_code,res.json()