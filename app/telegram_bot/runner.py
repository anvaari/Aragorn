"""aiogram bot lifecycle: long polling as an asyncio task in the FastAPI process."""
import asyncio
import time

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError

from core.config import app_settings
from log.logger import get_app_logger
from telegram_bot.handlers import admin, artists, common, events, reminders

logger = get_app_logger(__name__)

_POLL_TASK_NAME = "tg-bot-polling"
# Backoff between restart attempts after start_polling itself crashes (e.g. proxy
# down at startup). Mid-poll network errors are already retried inside aiogram's
# _listen_updates with its own backoff; this covers fatal startup failures.
_POLL_RESTART_BACKOFF = (2, 5, 15, 30, 60)

_poll_task: asyncio.Task | None = None


def _bot_session() -> AiohttpSession:
    """Session routed through tg_gpt_ig_proxy, same convention as telegram/bot.py:
    applied only when the value contains http."""
    proxy = app_settings.tg_gpt_ig_proxy
    if "http" in proxy:
        return AiohttpSession(proxy=proxy)
    return AiohttpSession()


def _new_bot() -> Bot:
    # Fresh Bot per attempt: start_polling closes the session on exit.
    return Bot(
        app_settings.telegram_bot_token,
        session=_bot_session(),
        default=DefaultBotProperties(parse_mode="Markdown"),
    )


def _new_dispatcher() -> Dispatcher:
    # Built once and reused: routers can only be attached to a single dispatcher.
    dispatcher = Dispatcher()
    dispatcher.include_routers(common.router, events.router,
                               artists.router, reminders.router, admin.router)
    return dispatcher


def start_bot_polling() -> asyncio.Task | None:
    """Start long polling; call from the lifespan (async context required).

    Only ONE polling process may run per bot token — Telegram returns 409
    conflicts otherwise. Set bot_enabled=false on secondary instances.
    """
    global _poll_task
    if not app_settings.bot_enabled:
        logger.info("Bot disabled (bot_enabled=false)")
        return None
    _poll_task = asyncio.create_task(_poll(), name=_POLL_TASK_NAME)
    logger.info("Telegram bot polling started")
    return _poll_task


async def _poll() -> None:
    """Run polling forever, restarting with backoff if it crashes."""
    dispatcher = _new_dispatcher()
    attempt = 0
    while True:
        bot = _new_bot()
        started = time.monotonic()
        try:
            # handle_signals=False: uvicorn owns SIGINT/SIGTERM (aiogram's default
            # handler would swallow Ctrl+C and the FastAPI process would never stop).
            await dispatcher.start_polling(bot, handle_signals=False)
            return  # graceful stop, not a crash
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if time.monotonic() - started > 60:
                attempt = 0  # was healthy for a while — treat as a fresh failure
            delay = _POLL_RESTART_BACKOFF[min(attempt, len(_POLL_RESTART_BACKOFF) - 1)]
            attempt += 1
            network_issue = isinstance(exc, TelegramNetworkError) or "proxy" in str(exc).lower()
            hint = " — is the tg_gpt_ig_proxy proxy running?" if network_issue else ""
            logger.error(f"Bot polling crashed (attempt {attempt}), restarting in {delay}s{hint}",
                         exc_info=True)
            await asyncio.sleep(delay)


async def stop_bot_polling(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        # Bounded wait: never let a stuck task block Ctrl+C shutdown forever.
        await asyncio.wait_for(asyncio.shield(task), timeout=5)
    except asyncio.TimeoutError:
        logger.warning("Bot polling task did not stop within 5s; abandoning it")
    except Exception:
        logger.info("Bot polling stopped")
