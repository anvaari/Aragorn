from instaloader import Instaloader,Post
from core.config import app_settings
from log.logger import get_app_logger
import os
import re


logger = get_app_logger(__name__)

def extract_caption(ig_link : str) -> str:
    # TODO: Better check for proxy
    """
    Extracts the caption from an Instagram post given its URL.
    
    Raises:
        ValueError: If the shortcode cannot be extracted from the URL or if the post caption is empty.
    
    Returns:
        The caption text of the Instagram post, followed by the original post URL.
    """
    if 'http://' in  app_settings.tg_gpt_ig_proxy:
        os.environ['http_proxy'] = app_settings.tg_gpt_ig_proxy
        os.environ['https_proxy'] = app_settings.tg_gpt_ig_proxy
    L = Instaloader()
    L.load_session_from_file(
        filename=app_settings.instaloader_login_file,
        username=app_settings.instagram_username
    )
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
    """
    Extracts the shortcode from an Instagram URL.
    
    Args:
    	ig_link: The Instagram post URL, which may be of type /p/, /reel/, or /tv/.
    
    Returns:
    	The extracted shortcode if present; otherwise, None.
    """
    match = re.search(r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)", ig_link)
    if match:
        return match.group(1)
    return None
