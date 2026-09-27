"""aiogram bot lifecycle: long polling as an asyncio task in the FastAPI process."""
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from core.config import app_settings
from log.logger import get_app_logger
from telegram_bot.handlers import artists, common, events, reminders

logger = get_app_logger(__name__)

_bot = None
_poll_task: asyncio.Task | None = None


def start_bot_polling() -> asyncio.Task | None:
    """Start long polling; call from the lifespan (async context required).

    Only ONE polling process may run per bot token — Telegram returns 409
    conflicts otherwise. Set bot_enabled=false on secondary instances.
    """
    global _bot, _poll_task
    if not app_settings.bot_enabled:
        logger.info("Bot disabled (bot_enabled=false)")
        return None
    _bot = Bot(
        app_settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode="Markdown"),
    )
    dispatcher = Dispatcher()
    dispatcher.include_routers(common.router, events.router,
                               artists.router, reminders.router)

    async def _poll() -> None:
        try:
            await dispatcher.start_polling(_bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.critical("Bot polling crashed",exc_info=True)

    _poll_task = asyncio.create_task(_poll(), name="tg-bot-polling")
    logger.info("Telegram bot polling started")
    return _poll_task


async def stop_bot_polling(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        logger.info("Bot polling stopped")