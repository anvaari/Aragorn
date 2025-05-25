from openai import OpenAI
from core.config import app_settings
import httpx

def get_openai_client():
    # TODO: Better check for proxy
    """
    Initializes and returns an OpenAI client, optionally configured with an HTTP proxy.
    
    If the application settings specify a proxy URL containing 'http://', the client is created with the proxy configuration; otherwise, it is created without a proxy.
    """
    if 'http://' in app_settings.tg_gpt_ig_proxy:
        client = OpenAI(
            api_key=app_settings.openai_api_key,
            http_client=httpx.Client(proxy=app_settings.tg_gpt_ig_proxy)
        )
    else:
        client = OpenAI(
            api_key=app_settings.openai_api_key
        )
    return client