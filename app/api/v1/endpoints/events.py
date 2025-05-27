from fastapi import APIRouter
from models.event import EventCreate
from services.event_service import post_manual_event_on_telegram,post_ig_event_on_telegram
from core.config import app_settings
from log.logger import get_app_logger
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


logger = get_app_logger(__name__)

router = APIRouter()
security = HTTPBearer()

def verify_bearer_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Validates the provided bearer token against the configured application token.
    
    Raises:
        HTTPException: If the token is invalid, an HTTP 403 Forbidden error is raised.
    """
    token = credentials.credentials
    if token != app_settings.aragorn_token:
        raise HTTPException(status_code=403, detail="Invalid token")


@router.post("/manual_event",dependencies=[Depends(verify_bearer_token)])
def manual_event(event: EventCreate):
    """
    Handles a manual event submission and posts it to Telegram.
    
    Args:
        event: The event data to be posted.
    
    Returns:
        The result of posting the event to Telegram.
    """
    return post_manual_event_on_telegram(event)

@router.post("/ig_event",dependencies=[Depends(verify_bearer_token)])
def ig_event(ig_link: str):
    """
    Posts an Instagram event to Telegram using the provided link.
    
    Args:
        ig_link: The URL of the Instagram event to be posted.
    
    Returns:
        The result of posting the Instagram event to Telegram.
    """
    return post_ig_event_on_telegram(ig_link)
