from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from telegram_bot.callbacks import (ArtistsOfCB, ArtistCB, DayCB, EventCB,
                                    FollowCB, FollowPrefCB, MenuCB, RemindDelCB,
                                    RemindHoursCB, RemindSetCB, UnfollowCB)
from utils.event_time import jday_short_label

_MAX_BUTTON_TITLE = 48
_DAY_WINDOW = 7  # browseable days ahead


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 رویدادها", callback_data=MenuCB(action="events").pack()),
        InlineKeyboardButton(text="🎤 هنرمندان", callback_data=MenuCB(action="artists").pack()),
    )
    builder.row(
        InlineKeyboardButton(text="🔔 یادآورها", callback_data=MenuCB(action="reminders").pack()),
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
    builder.row(
        InlineKeyboardButton(text="👥 هنرمندان این اجرا", callback_data=ArtistsOfCB(event_id=event_id).pack()),
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


def event_artists_keyboard(event_id: int, artists: list[dict]) -> InlineKeyboardMarkup:
    """Buttons for linked artists; unresolved raw names stay plain text in the message."""
    builder = InlineKeyboardBuilder()
    for artist in artists:
        builder.row(InlineKeyboardButton(
            text=f"🎤 {_short(artist['name'])}",
            callback_data=ArtistCB(artist_id=artist["id"]).pack(),
        ))
    builder.row(InlineKeyboardButton(
        text="🔙 بازگشت", callback_data=EventCB(event_id=event_id).pack()))
    return builder.as_markup()


def artist_card_keyboard(artist_id: int, is_following: bool,
                         follow_id: int | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_following and follow_id is not None:
        builder.row(InlineKeyboardButton(
            text="➖ لغو دنبال کردن", callback_data=UnfollowCB(follow_id=follow_id).pack()))
    elif not is_following:
        builder.row(InlineKeyboardButton(
            text="➕ دنبال کردن هنرمند", callback_data=FollowCB(artist_id=artist_id).pack()))
    builder.row(InlineKeyboardButton(
        text="🎤 جستجوی هنرمند", callback_data=MenuCB(action="artists").pack()))
    builder.row(InlineKeyboardButton(
        text="🏠 منوی اصلی", callback_data=MenuCB(action="main").pack()))
    return builder.as_markup()


def follow_pref_keyboard(artist_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔔 رویداد جدید", callback_data=FollowPrefCB(artist_id=artist_id, mode="new").pack()),
    )
    builder.row(
        InlineKeyboardButton(text="⏰ یادآوری قبل از اجرا", callback_data=FollowPrefCB(artist_id=artist_id, mode="pre").pack()),
    )
    builder.row(
        InlineKeyboardButton(text="✅ هر دو", callback_data=FollowPrefCB(artist_id=artist_id, mode="both").pack()),
    )
    builder.row(InlineKeyboardButton(
        text="🔙 بازگشت", callback_data=ArtistCB(artist_id=artist_id).pack()))
    return builder.as_markup()


def reminders_list_keyboard(reminders: list[dict], follows: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for reminder in reminders:
        builder.row(InlineKeyboardButton(
            text=f"❌ یادآوری {_short(reminder['event_title'] or 'رویداد', 36)}",
            callback_data=RemindDelCB(reminder_id=reminder["id"]).pack(),
        ))
    for follow in follows:
        builder.row(InlineKeyboardButton(
            text=f"➖ {_short(follow['artist_name'], 36)}",
            callback_data=UnfollowCB(follow_id=follow["id"]).pack(),
        ))
    builder.row(InlineKeyboardButton(
        text="🏠 منوی اصلی", callback_data=MenuCB(action="main").pack()))
    return builder.as_markup()