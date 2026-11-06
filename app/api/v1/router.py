from fastapi import APIRouter
from .endpoints import events, miniapp

router = APIRouter()
router.include_router(events.router, prefix="/events", tags=["events"])
router.include_router(miniapp.router, prefix="/miniapp", tags=["miniapp"])
