from instaloader import Instaloader,Post
from core.config import app_settings
from log.logger import get_app_logger
import os
import re


logger = get_app_logger(__name__)

def extract_caption(ig_link : str) -> str:
    # TODO: Better check for proxy
    if 'http://' in  app_settings.tg_gpt_ig_proxy:
        os.environ['http_proxy'] = app_settings.tg_gpt_ig_proxy
        os.environ['https_proxy'] = app_settings.tg_gpt_ig_proxy
    L = Instaloader()
    ig_short = extract_short_code_from_ig_link(ig_link)
    if not ig_short:
        raise ValueError(
            "Can't Extract short code from given url.\n"
            f"link: {ig_link}"
        )
    post = Post.from_shortcode(L.context,ig_short)
    content = post.caption

    os.environ['http_proxy'] = ""
    os.environ['https_proxy'] = ""

    if not content :
        # TODO: Better error handling
        raise ValueError(
            f"Content for post: {ig_link} was empty"
        )

    return content+f"\n{ig_link}"



def extract_short_code_from_ig_link(ig_link:str) -> None|str:
    match = re.search(r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)", ig_link)
    if match:
        return match.group(1)
    return None
