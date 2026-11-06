from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.config import app_settings
from telegram_bot.callbacks import (ArtistReviewCB, DayCB, EventCB, MenuCB,
                                    RemindDelCB, RemindHoursCB, RemindSetCB)
from utils.event_time import jday_short_label

_MAX_BUTTON_TITLE = 48
_DAY_WINDOW = 7  # browseable days ahead


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 رویدادها", callback_data=MenuCB(action="events").pack()),
    )
    builder.row(
        InlineKeyboardButton(text="🔔 یادآورها", callback_data=MenuCB(action="reminders").pack()),
    )
    if app_settings.miniapp_url:
        builder.row(InlineKeyboardButton(
            text="🎨 حمایت از هنرمندان", web_app=WebAppInfo(url=app_settings.miniapp_url)))
    return builder.as_markup()


def artist_review_keyboard(artist_id: int, revision: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ تأیید", callback_data=ArtistReviewCB(
            artist_id=artist_id, revision=revision, approve=True).pack()),
        InlineKeyboardButton(text="❌ رد", callback_data=ArtistReviewCB(
            artist_id=artist_id, revision=revision, approve=False).pack()),
    )
    return builder.as_markup()


def day_picker_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for offset in range(_DAY_WINDOW):
        builder.button(
            text=jday_short_label(offset),
            callback_data=DayCB(offset=offset).pack(),
        )
    builder.adjust(2)
    builder.row(InlineKeyboardButton(
        text="🔎 جستجو با تاریخ", callback_data=MenuCB(action="date").pack()))
    builder.row(InlineKeyboardButton(
        text="🏠 منوی اصلی", callback_data=MenuCB(action="main").pack()))
    return builder.as_markup()


def _short(text: str, limit: int = _MAX_BUTTON_TITLE) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def day_events_keyboard(events: list[tuple[int, object]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for event_id, event in events:
        builder.row(InlineKeyboardButton(
            text=f"🎤 {_short(event.title or 'بدون عنوان')}",
            callback_data=EventCB(event_id=event_id).pack(),
        ))
    builder.row(InlineKeyboardButton(
        text="📅 روزهای دیگر", callback_data=MenuCB(action="events").pack()))
    return builder.as_markup()


def event_card_keyboard(event_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔔 یادآوری این رویداد", callback_data=RemindSetCB(event_id=event_id).pack()),
    )
    builder.row(InlineKeyboardButton(
        text="📅 روزهای دیگر", callback_data=MenuCB(action="events").pack()))
    return builder.as_markup()


def reminder_choice_keyboard(event_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏰ ۲ ساعت قبل", callback_data=RemindHoursCB(event_id=event_id, hours=2).pack()),
        InlineKeyboardButton(text="🗓 ۲۴ ساعت قبل", callback_data=RemindHoursCB(event_id=event_id, hours=24).pack()),
    )
    builder.row(
        InlineKeyboardButton(text="✅ هر دو", callback_data=RemindHoursCB(event_id=event_id, hours=0).pack()),
    )
    builder.row(InlineKeyboardButton(
        text="🔙 بازگشت", callback_data=EventCB(event_id=event_id).pack()))
    return builder.as_markup()


def reminders_list_keyboard(reminders: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for reminder in reminders:
        builder.row(InlineKeyboardButton(
            text=f"❌ یادآوری {_short(reminder['event_title'] or 'رویداد', 36)}",
            callback_data=RemindDelCB(reminder_id=reminder["id"]).pack(),
        ))
    builder.row(InlineKeyboardButton(
        text="🏠 منوی اصلی", callback_data=MenuCB(action="main").pack()))
    return builder.as_markup()