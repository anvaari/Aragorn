import requests
from core.config import app_settings
from log.logger import get_app_logger

logger = get_app_logger(__name__)

def send_to_telegram(text):
    token = app_settings.telegram_bot_token
    chat_id = app_settings.telegram_chat_id
    proxy = "http://127.0.0.1:20170"
    proxies = {'http':proxy,'https':proxy}
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
