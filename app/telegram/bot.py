import requests
from core.config import app_settings
from log.logger import get_app_logger

logger = get_app_logger(__name__)

def send_text_to_telegram(text):
    token = app_settings.telegram_bot_token
    chat_id = app_settings.telegram_chat_id
    proxy = app_settings.tg_gpt_ig_proxy
    # TODO: Better check for proxy
    if 'http' in proxy :
        proxies = {'http':proxy,'https':proxy}
    else:
        proxies = {}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id, 
        "text": text,
        "parse_mode": "Markdown"
    }
    res = requests.post(
        url, 
        data=data,
        proxies=proxies
    )
    return res.status_code,res.json()

def send_image_to_telegram(text:str,photo:str|bytes):
    token = app_settings.telegram_bot_token
    chat_id = app_settings.telegram_chat_id
    proxy = app_settings.tg_gpt_ig_proxy

    # TODO: Better check for proxy
    if 'http' in proxy :
        proxies = {'http':proxy,'https':proxy}
    else:
        proxies = {}
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