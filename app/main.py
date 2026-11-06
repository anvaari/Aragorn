from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.v1 import router as api_router
from core.scheduler import (shutdown_scheduler, start_bot_scheduler,
                            start_digest_scheduler)
from telegram_bot.runner import start_bot_polling, stop_bot_polling


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = start_digest_scheduler()
    bot_scheduler = start_bot_scheduler()
    bot_task = start_bot_polling()
    yield
    await stop_bot_polling(bot_task)
    shutdown_scheduler(bot_scheduler)
    shutdown_scheduler(scheduler)


app = FastAPI(title="Aragorn - Independent Music Event Collector", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router.router, prefix="/api/v1")
# Telegram Mini App (static page); Telegram requires this to be reachable over HTTPS.
app.mount("/miniapp", StaticFiles(directory=Path(__file__).parent / "miniapp", html=True), name="miniapp")