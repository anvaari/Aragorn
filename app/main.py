from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.v1 import router as api_router
from core.scheduler import start_digest_scheduler, shutdown_digest_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = start_digest_scheduler()
    yield
    shutdown_digest_scheduler(scheduler)


app = FastAPI(title="Aragorn - Independent Music Event Collector", lifespan=lifespan)
app.include_router(api_router.router, prefix="/api/v1")
