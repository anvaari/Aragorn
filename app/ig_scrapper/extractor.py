from instaloader import Instaloader,Post
from core.config import app_settings
from log.logger import get_app_logger
import os
import re
import json


logger = get_app_logger(__name__)

def extract_caption_image(ig_link : str) -> tuple[str,str]:
    # TODO: Better check for proxy
    if 'http://' in  app_settings.tg_gpt_ig_proxy:
        os.environ['http_proxy'] = app_settings.tg_gpt_ig_proxy
        os.environ['https_proxy'] = app_settings.tg_gpt_ig_proxy
    
    insta_cookie = json.loads(app_settings.instagram_login_cookie)
    L = Instaloader()
    L.load_session(
        "anvaari",
        insta_cookie
    )
    ig_short = extract_short_code_from_ig_link(ig_link)
    if not ig_short:
        raise ValueError(
            "Can't Extract short code from given url.\n"
            f"link: {ig_link}"
        )
    post = Post.from_shortcode(L.context,ig_short)
    content = post.caption
    if post.typename == "GraphImage":
        media_url = post.url  # photo
    elif post.typename == "GraphVideo":
        media_url = post.video_url or post.url  # fallback to thumbnail if video
    elif post.typename == "GraphSidecar":  # carousel (multiple media)
        media_url = list(post.get_sidecar_nodes())[0].display_url
    else:
        media_url = post.url  # fallback

    os.environ['http_proxy'] = ""
    os.environ['https_proxy'] = ""

    if not content :
        # TODO: Better error handling
        raise ValueError(
            f"Content for post: {ig_link} was empty"
        )

    return content+f"\n{ig_link}",media_url



def extract_short_code_from_ig_link(ig_link:str) -> None|str:
    match = re.search(r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)", ig_link)
    if match:
        return match.group(1)
    return None
