from fastapi import APIRouter
from .endpoints import events

router = APIRouter()
router.include_router(events.router, prefix="/events", tags=["events"])
