from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from db import crud_bot
from db.crud_artist import get_event_artists
from db.crud_event import get_event_by_id, get_events_by_jdate_with_ids
from log.logger import get_app_logger
from telegram_bot.callbacks import (ArtistsOfCB, DayCB, EventCB, RemindHoursCB,
                                    RemindSetCB)
from telegram_bot.cards import _escape_md, format_event_card
from telegram_bot.handlers.common import DAY_PICKER_TEXT, safe_edit
from telegram_bot.keyboards import (day_events_keyboard, day_picker_keyboard,
                                    event_artists_keyboard, event_card_keyboard,
                                    reminder_choice_keyboard)
from utils.event_time import (event_remind_at, jdate_for_offset, jday_full_label,
                              now_tehran, parse_event_datetime)

logger = get_app_logger(__name__)

router = Router()

_REMINDER_HOURS = (2, 24)  # "هر دو" creates both


@router.message(Command("events"))
async def cmd_events(message: Message) -> None:
    await message.answer(DAY_PICKER_TEXT, reply_markup=day_picker_keyboard())


@router.callback_query(DayCB.filter())
async def show_day(callback: CallbackQuery, callback_data: DayCB) -> None:
    jdate, _weekday = jdate_for_offset(callback_data.offset)
    label = jday_full_label(callback_data.offset)
    events = get_events_by_jdate_with_ids(jdate)
    if not events:
        text = f"🗓 *{label}*\n\n_برای این روز رویدادی ثبت نشده است._"
        await safe_edit(callback, text, day_picker_keyboard())
    else:
        lines = [f"🗓 *رویدادهای {label}* — {len(events)} رویداد", ""]
        for _event_id, event in events:
            lines.append(f"• {_escape_md(event.title or 'بدون عنوان')} — {event.time}")
        await safe_edit(callback, "\n".join(lines), day_events_keyboard(events))
    await callback.answer()


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


@router.callback_query(ArtistsOfCB.filter())
async def show_event_artists(callback: CallbackQuery, callback_data: ArtistsOfCB) -> None:
    event = get_event_by_id(callback_data.event_id)
    if not event:
        await callback.answer("🤔 رویداد مورد نظر پیدا نشد.", show_alert=True)
        return
    artists = get_event_artists(callback_data.event_id)
    if not artists:
        # nothing linked yet: show the raw performers text
        raw_names = [name.strip() for name in event.performers.split(",") if name.strip()]
        text = f"👥 *هنرمندان {_escape_md(event.title or 'بدون عنوان')}:*"
        if raw_names:
            text += "\n\n" + " · ".join(_escape_md(name) for name in raw_names)
        else:
            text += "\n_هنوز هنرمندی ثبت نشده است._"
        await safe_edit(callback, text, event_card_keyboard(callback_data.event_id))
        await callback.answer()
        return

    raw_names = [a["artist_name_raw"] for a in artists if a.get("artist_name_raw")]
    lines = ["👥 *هنرمندان این اجرا* (برای اطلاعات و دنبال کردن انتخاب کنید):"]
    if raw_names:
        lines.append("")
        lines.append(" · ".join(_escape_md(name) for name in raw_names))
    await safe_edit(callback, "\n".join(lines),
                    event_artists_keyboard(callback_data.event_id, artists))
    await callback.answer()