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
    token = credentials.credentials
    if token != app_settings.aragorn_token:
        raise HTTPException(status_code=403, detail="Invalid token")


@router.post("/manual_event",dependencies=[Depends(verify_bearer_token)])
def manual_event(event: EventCreate):
    return post_manual_event_on_telegram(event)

@router.post("/ig_event",dependencies=[Depends(verify_bearer_token)])
def ig_event(ig_link: str):
    return post_ig_event_on_telegram(ig_link)
