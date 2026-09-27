from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db import crud_bot
from db.crud_artist import get_artist, get_events_for_artist, search_artists
from db.crud_event import get_events_like_performer_with_ids
from log.logger import get_app_logger
from telegram_bot.callbacks import (ArtistCB, EventCB, FollowCB, FollowPrefCB,
                                    MenuCB, UnfollowCB)
from telegram_bot.cards import _escape_md, format_artist_card
from telegram_bot.handlers.common import safe_edit
from telegram_bot.keyboards import (artist_card_keyboard, follow_pref_keyboard)
from utils.event_time import now_tehran, parse_event_datetime

logger = get_app_logger(__name__)

router = Router()

_MAX_ARTIST_BUTTONS = 8
_MAX_EVENT_MATCHES = 6
_MAX_PAST_SHOWN = 5

ASK_ARTIST_TEXT = "🎤 *نام هنرمند را بنویسید:*\n\n_مثلاً: Sun Spots Band_"
NOT_FOUND_TEXT = "_هنرمندی با این نام پیدا نشد._\nممکن است هنوز رویدادی از این هنرمند ثبت نشده باشد."


class ArtistSearch(StatesGroup):
    waiting_name = State()


@router.message(Command("artist"))
async def cmd_artist(message: Message, state: FSMContext) -> None:
    await state.set_state(ArtistSearch.waiting_name)
    await message.answer(ASK_ARTIST_TEXT)


@router.callback_query(MenuCB.filter(F.action == "artists"))
async def menu_artists(callback: CallbackQuery, callback_data: MenuCB, state: FSMContext) -> None:
    await state.set_state(ArtistSearch.waiting_name)
    await safe_edit(callback, ASK_ARTIST_TEXT, None)
    await callback.answer()


@router.message(ArtistSearch.waiting_name, F.text)
async def artist_search(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    await state.clear()
    if not query:
        await message.answer("🤔 نامی وارد نشد. دوباره تلاش کنید.")
        return

    artist_rows = search_artists(query)
    event_matches = get_events_like_performer_with_ids(query)

    keyboard = InlineKeyboardBuilder()
    lines = [f"🎤 *نتایج جستجو برای «{_escape_md(query)}»:*"]
    if artist_rows:
        lines.append("")
        for artist in artist_rows[:_MAX_ARTIST_BUTTONS]:
            keyboard.row(InlineKeyboardButton(
                text=f"🎤 {artist['name']}",
                callback_data=ArtistCB(artist_id=artist["id"]).pack(),
            ))
    if event_matches:
        lines.append("")
        lines.append("🗓 *رویدادهای مرتبط:*")
        for event_id, event in event_matches[:_MAX_EVENT_MATCHES]:
            keyboard.row(InlineKeyboardButton(
                text=f"🗓 {(event.title or 'بدون عنوان')[:40]}",
                callback_data=EventCB(event_id=event_id).pack(),
            ))
    if not artist_rows and not event_matches:
        lines.append("")
        lines.append(NOT_FOUND_TEXT)
    keyboard.row(InlineKeyboardButton(
        text="🏠 منوی اصلی", callback_data=MenuCB(action="main").pack()))
    await message.answer("\n".join(lines), reply_markup=keyboard.as_markup())


def _split_events(events: list[tuple[int, object]]) -> tuple[list, list, list]:
    """Split (id, event) pairs into upcoming / past / unknown-date lists."""
    now = now_tehran()
    upcoming, past, unknown = [], [], []
    for event_id, event in events:
        dt = parse_event_datetime(event.datetime)
        if dt is None:
            unknown.append((event_id, event))
        elif dt >= now:
            upcoming.append((dt, event_id, event))
        else:
            past.append((dt, event_id, event))
    upcoming.sort(key=lambda item: item[0])
    past.sort(key=lambda item: item[0], reverse=True)
    upcoming = [(event_id, event) for _, event_id, event in upcoming]
    past = [(event_id, event) for _, event_id, event in past[:_MAX_PAST_SHOWN]]
    return upcoming, past, unknown


@router.callback_query(ArtistCB.filter())
async def show_artist(callback: CallbackQuery, callback_data: ArtistCB) -> None:
    artist = get_artist(callback_data.artist_id)
    if not artist:
        await callback.answer("🤔 هنرمند مورد نظر پیدا نشد.", show_alert=True)
        return
    events = get_events_for_artist(callback_data.artist_id)
    upcoming, past, unknown = _split_events(events)
    follow = crud_bot.get_follow(callback.from_user.id, callback_data.artist_id)
    text = format_artist_card(artist, upcoming, past, unknown)
    await safe_edit(
        callback, text,
        artist_card_keyboard(callback_data.artist_id,
                             is_following=follow is not None,
                             follow_id=follow["id"] if follow else None))
    await callback.answer()


@router.callback_query(FollowCB.filter())
async def ask_follow_pref(callback: CallbackQuery, callback_data: FollowCB) -> None:
    await safe_edit(callback,
                    "🔔 *چه اطلاعاتی برای این هنرمند می‌خواهید؟*",
                    follow_pref_keyboard(callback_data.artist_id))
    await callback.answer()


_FOLLOW_MODES = {"new": (True, False), "pre": (False, True), "both": (True, True)}


@router.callback_query(FollowPrefCB.filter())
async def save_follow(callback: CallbackQuery, callback_data: FollowPrefCB) -> None:
    artist = get_artist(callback_data.artist_id)
    if not artist:
        await callback.answer("🤔 هنرمند مورد نظر پیدا نشد.", show_alert=True)
        return
    notify_new, notify_pre = _FOLLOW_MODES.get(callback_data.mode, (True, False))
    crud_bot.upsert_artist_follow(callback.from_user.id, callback_data.artist_id,
                                  notify_new=notify_new, notify_pre=notify_pre)
    await safe_edit(callback, format_artist_card(
        artist, *_split_events(get_events_for_artist(callback_data.artist_id))),
        artist_card_keyboard(callback_data.artist_id, is_following=True,
                             follow_id=_follow_id(callback.from_user.id, callback_data.artist_id)))
    await callback.answer("✅ ثبت شد!")


def _follow_id(chat_id: int, artist_id: int) -> int | None:
    follow = crud_bot.get_follow(chat_id, artist_id)
    return follow["id"] if follow else None


@router.callback_query(UnfollowCB.filter())
async def unfollow(callback: CallbackQuery, callback_data: UnfollowCB) -> None:
    deleted = crud_bot.delete_follow(callback_data.follow_id, callback.from_user.id)
    if deleted:
        await callback.answer("➖ دنبال کردن لغو شد.", show_alert=True)
    else:
        await callback.answer("ℹ️ این دنبال کردن قبلاً لغو شده است.", show_alert=True)