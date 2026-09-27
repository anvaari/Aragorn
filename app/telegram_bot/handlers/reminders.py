from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from db import crud_bot
from log.logger import get_app_logger
from telegram_bot.callbacks import MenuCB, RemindDelCB
from telegram_bot.cards import _escape_md
from telegram_bot.handlers.common import safe_edit
from telegram_bot.keyboards import reminders_list_keyboard
from utils.event_time import fa_digits, format_jdatetime

logger = get_app_logger(__name__)

router = Router()


def _build_reminders_text(chat_id: int) -> tuple[str, list[dict], list[dict]]:
    reminders = crud_bot.get_user_reminders(chat_id)
    follows = crud_bot.get_user_follows(chat_id)
    lines = ["🔔 *یادآورهای فعال شما:*"]
    if reminders:
        for reminder in reminders:
            title = reminder.get("event_title") or "رویداد"
            when = format_jdatetime(reminder.get("remind_at"))
            lines.append(f"⏰ {_escape_md(title)} — {when}")
    else:
        lines.append("_یادآوری رویدادی ثبت نکرده‌اید._")
    lines.append("")
    lines.append("🎤 *هنرمندهای دنبال‌شده:*")
    if follows:
        for follow in follows:
            badges = []
            if follow["notify_new"]:
                badges.append("رویداد جدید")
            if follow["notify_pre"]:
                badges.append(f"یادآوری {fa_digits(follow['pre_hours'] or 2)} ساعت قبل")
            lines.append(f"• {_escape_md(follow['artist_name'])} ({' + '.join(badges)})")
    else:
        lines.append("_هنرمندی را دنبال نمی‌کنید._")
    lines.append("")
    lines.append("برای حذف، روی مورد موردنظر بزنید:")
    return "\n".join(lines), reminders, follows


@router.message(Command("reminders"))
async def cmd_reminders(message: Message) -> None:
    text, reminders, follows = _build_reminders_text(message.chat.id)
    await message.answer(text, reply_markup=reminders_list_keyboard(reminders, follows))


@router.callback_query(MenuCB.filter(F.action == "reminders"))
async def menu_reminders(callback: CallbackQuery, callback_data: MenuCB) -> None:
    text, reminders, follows = _build_reminders_text(callback.from_user.id)
    await safe_edit(callback, text, reminders_list_keyboard(reminders, follows))
    await callback.answer()


@router.callback_query(RemindDelCB.filter())
async def delete_reminder(callback: CallbackQuery, callback_data: RemindDelCB) -> None:
    deleted = crud_bot.delete_reminder(callback_data.reminder_id, callback.from_user.id)
    if deleted:
        await callback.answer("❌ یادآوری حذف شد.", show_alert=True)
    else:
        await callback.answer("ℹ️ این یادآوری قبلاً حذف شده است.", show_alert=True)
    if callback.message:
        text, reminders, follows = _build_reminders_text(callback.from_user.id)
        try:
            await callback.message.edit_text(text, reply_markup=reminders_list_keyboard(reminders, follows))
        except Exception:
            pass