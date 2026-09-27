from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.filters.command import CommandObject
from aiogram.types import CallbackQuery, Message

from db import crud_bot
from db.crud_event import get_event_by_id
from log.logger import get_app_logger
from telegram_bot.callbacks import MenuCB
from telegram_bot.cards import format_event_card
from telegram_bot.keyboards import day_picker_keyboard, event_card_keyboard, main_menu_keyboard

logger = get_app_logger(__name__)

router = Router()

WELCOME_TEXT = (
    "👋 سلام! من ربات *آرگورن* هستم.\n\n"
    "🎵 می‌تونید رویدادهای موسیقی مستقل رو مرور کنید، هنرمندها رو جستجو کنید و "
    "برای رویدادها یا هنرمندهای دلخواه‌تون یادآوری بذارید.\n\n"
    "از منوی زیر شروع کنید:"
)

DAY_PICKER_TEXT = "📅 *یک روز را انتخاب کنید:*"


def _register_user(message: Message) -> None:
    crud_bot.upsert_bot_user(
        chat_id=message.chat.id,
        username=message.from_user.username if message.from_user else None,
        first_name=message.from_user.first_name if message.from_user else None,
    )


async def safe_edit(callback, text: str, reply_markup) -> None:
    """edit_text that tolerates 'message is not modified' and un-editable messages."""
    if not callback.message:
        return
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject) -> None:
    _register_user(message)
    deep_link = (command.args or "").strip()
    if deep_link.startswith("evt_"):
        try:
            event_id = int(deep_link[len("evt_"):])
        except ValueError:
            event_id = None
        if event_id is not None:
            event = get_event_by_id(event_id)
            if event:
                await message.answer(
                    format_event_card(event),
                    reply_markup=event_card_keyboard(event_id),
                )
                return
        await message.answer("🤔 رویداد مورد نظر پیدا نشد.")
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard())


@router.callback_query(MenuCB.filter(F.action == "main"))
async def menu_main(callback: CallbackQuery, callback_data: MenuCB) -> None:
    await safe_edit(callback, WELCOME_TEXT, main_menu_keyboard())
    await callback.answer()


@router.callback_query(MenuCB.filter(F.action == "events"))
async def menu_events(callback: CallbackQuery, callback_data: MenuCB) -> None:
    await safe_edit(callback, DAY_PICKER_TEXT, day_picker_keyboard())
    await callback.answer()