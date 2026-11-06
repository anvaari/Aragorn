import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from db import crud_bot
from db.crud_event import get_event_by_id, get_events_by_jdate_with_ids
from log.logger import get_app_logger
from telegram_bot.callbacks import DayCB, EventCB, MenuCB, RemindHoursCB, RemindSetCB
from telegram_bot.cards import _escape_md, format_event_card
from telegram_bot.handlers.common import DAY_PICKER_TEXT, safe_edit
from telegram_bot.keyboards import (day_events_keyboard, day_picker_keyboard,
                                    event_card_keyboard, reminder_choice_keyboard)
from utils.event_time import (event_remind_at, fa_digits, jdate_for_offset,
                              jdate_full_label, jday_full_label, now_tehran,
                              parse_event_datetime, parse_shamsi_date)

logger = get_app_logger(__name__)

router = Router()

_REMINDER_HOURS = (2, 24)  # "هر دو" creates both

_DATE_PROMPT_TEXT = (
    "📅 *تاریخ شمسی را بنویسید*\n\n"
    "مثال: `1405-08-25`\n"
    "با ارقام فارسی هم می‌شود: `۱۴۰۵/۰۸/۲۵`"
)

_DATE_LIKE_RE = re.compile(r"^[\d۰-۹٠-٩\s\-/.]+$")


def _looks_like_date(text: str) -> bool:
    """True for date-ish input, so ordinary chatter is ignored instead of answered."""
    return bool(_DATE_LIKE_RE.match(text)) and sum(ch.isdigit() for ch in text) >= 3


def _day_view(jdate: str, label: str):
    """Message text + keyboard for one Shamsi date."""
    events = get_events_by_jdate_with_ids(jdate)
    if not events:
        return f"🗓 {label}\n\n_برای این روز رویدادی ثبت نشده است._", day_picker_keyboard()
    lines = [f"🗓 {label} — {fa_digits(len(events))} رویداد", ""]
    for _event_id, event in events:
        lines.append(f"• {_escape_md(event.title or 'بدون عنوان')} — `{event.time}`")
    return "\n".join(lines), day_events_keyboard(events)


@router.message(Command("events"))
async def cmd_events(message: Message) -> None:
    await message.answer(DAY_PICKER_TEXT, reply_markup=day_picker_keyboard())


@router.callback_query(DayCB.filter())
async def show_day(callback: CallbackQuery, callback_data: DayCB) -> None:
    jdate, _weekday = jdate_for_offset(callback_data.offset)
    text, keyboard = _day_view(jdate, jday_full_label(callback_data.offset))
    await safe_edit(callback, text, keyboard)
    await callback.answer()


@router.callback_query(MenuCB.filter(F.action == "date"))
async def ask_date(callback: CallbackQuery, callback_data: MenuCB) -> None:
    await safe_edit(callback, _DATE_PROMPT_TEXT, day_picker_keyboard())
    await callback.answer()


@router.message(F.text & ~F.text.startswith("/"))
async def search_by_date(message: Message) -> None:
    """Let users type a Shamsi date (e.g. 1405-08-25) to see that day's events."""
    jdate = parse_shamsi_date(message.text)
    if jdate is None:
        if _looks_like_date(message.text or ""):
            await message.answer("😕 تاریخ معتبر نیست. نمونه: `1405-08-25`")
        return
    text, keyboard = _day_view(jdate, jdate_full_label(jdate))
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(EventCB.filter())
async def show_event(callback: CallbackQuery, callback_data: EventCB) -> None:
    event = get_event_by_id(callback_data.event_id)
    if not event:
        await callback.answer("🤔 رویداد مورد نظر پیدا نشد.", show_alert=True)
        return
    await safe_edit(callback, format_event_card(event),
                    event_card_keyboard(callback_data.event_id))
    await callback.answer()


@router.callback_query(RemindSetCB.filter())
async def choose_reminder(callback: CallbackQuery, callback_data: RemindSetCB) -> None:
    event = get_event_by_id(callback_data.event_id)
    if not event:
        await callback.answer("🤔 رویداد مورد نظر پیدا نشد.", show_alert=True)
        return
    if callback.message:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=reminder_choice_keyboard(callback_data.event_id))
        except Exception:
            logger.error("Can't swap event card keyboard for reminder choice",exc_info=True)
    await callback.answer("⏰ کی یادت بندازیم؟")


@router.callback_query(RemindHoursCB.filter())
async def set_reminder(callback: CallbackQuery, callback_data: RemindHoursCB) -> None:
    event = get_event_by_id(callback_data.event_id)
    if not event:
        await callback.answer("🤔 رویداد مورد نظر پیدا نشد.", show_alert=True)
        return
    if callback.message is None:
        await callback.answer()
        return
    event_dt = parse_event_datetime(event.datetime)
    if event_dt is None:
        await callback.answer(
            "😕 زمان این رویداد مشخص نیست و یادآوری ممکن نیست.", show_alert=True)
        return
    if event_dt <= now_tehran():
        await callback.answer("🕰 این رویداد گذشته یا در حال برگزاری است.", show_alert=True)
        return

    hours_list = _REMINDER_HOURS if callback_data.hours == 0 else (callback_data.hours,)
    created = 0
    for hours in hours_list:
        remind_dt = event_remind_at(event_dt, hours)
        if remind_dt <= now_tehran():
            continue
        if crud_bot.add_event_reminder(
                callback.message.chat.id, callback_data.event_id,
                remind_at=remind_dt.strftime("%Y-%m-%d %H:%M")):
            created += 1

    if created:
        chosen = " و ".join(f"{hours} ساعت قبل" for hours in hours_list)
        try:
            await callback.message.edit_reply_markup(
                reply_markup=event_card_keyboard(callback_data.event_id))
        except Exception:
            pass
        await callback.answer(f"✅ یادآوری ثبت شد: {chosen}", show_alert=True)
    else:
        await callback.answer("ℹ️ این یادآوری قبلاً ثبت شده است.", show_alert=True)