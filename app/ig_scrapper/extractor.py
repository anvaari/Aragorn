from instagrapi import Client
from instagrapi.exceptions import ClientError
from pydantic.networks import HttpUrl
from core.config import app_settings
from log.logger import get_app_logger
from fastapi import HTTPException


logger = get_app_logger(__name__)



def extract_caption_image(ig_link: str) -> tuple[str, str]:
    """
    Extract caption and media URL from Instagram post using instagrapi.
    
    Args:
        ig_link: Instagram post URL
        
    Returns:
        tuple: (caption with link, media_url)
    """
    cl = Client()
    
    if 'http://' in app_settings.tg_gpt_ig_proxy:
        cl.set_proxy(app_settings.tg_gpt_ig_proxy) 
    try:

        cl.load_settings(app_settings.instagram_login_session_file)
        media_pk = cl.media_pk_from_url(ig_link)        
        media = cl.media_info(media_pk)
        
        # Extract caption
        content = media.caption_text or ""

        # Extract media URL based on type
        if media.media_type == 1:  # Photo
            media_url = media.thumbnail_url
        elif media.media_type == 2:  # Video
            media_url = media.thumbnail_url  # or media.video_url for actual video
        elif media.media_type == 8:  # Carousel/Album
            # Get first item from carousel
            media_url = media.resources[0].thumbnail_url if media.resources else media.thumbnail_url
        else:
            media_url = media.thumbnail_url
        
        if media_url is str:
            pass
        elif media_url is None:
            media_url = ""
            logger.warning(f"Media URL for post {ig_link} is None")
        elif isinstance(media_url, HttpUrl):
            media_url = media_url.__str__()
        if not content:
            raise HTTPException(status_code=500,detail=f"Content for post: {ig_link} was empty")
        return content + f"\n{ig_link}", media_url
    
    except ClientError as e:
        raise HTTPException(status_code=500,detail=f"Failed to fetch Instagram post: {ig_link}. Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500,detail=f"Unexpected error processing {ig_link}: {str(e)}")
