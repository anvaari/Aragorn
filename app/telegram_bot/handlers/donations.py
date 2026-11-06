"""Telegram Stars checkout and admin review of artist claims (the Mini App does the rest)."""
import asyncio

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery

from core.config import app_settings
from db import crud_donation
from log.logger import get_app_logger
from services import donation_service
from telegram_bot.callbacks import ArtistReviewCB
from telegram_bot.cards import format_artist_review_result

logger = get_app_logger(__name__)

router = Router()


def _artist_id_from_payload(payload: str) -> int | None:
    """Invoice payloads are 'artist:<id>' (see donation_service.create_stars_invoice)."""
    prefix, _, artist_id = payload.partition(":")
    return int(artist_id) if prefix == "artist" and artist_id.isdigit() else None


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    # Telegram cancels the payment unless this is answered within 10 seconds.
    artist_id = _artist_id_from_payload(query.invoice_payload)
    artist = crud_donation.get_artist(artist_id) if artist_id is not None else None
    if artist and artist["status"] == "approved":
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="این هنرمند در حال حاضر حمایت دریافت نمی‌کند.")


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    payment = message.successful_payment
    artist_id = _artist_id_from_payload(payment.invoice_payload)
    if artist_id is None:
        logger.error(f"Stars payment with unknown payload={payment.invoice_payload!r} "
                     f"charge_id={payment.telegram_payment_charge_id}")
        return
    await asyncio.to_thread(donation_service.record_stars_donation, artist_id, message.chat.id,
                            payment.total_amount, payment.telegram_payment_charge_id)
    await message.answer("🙏 *ممنون از حمایت شما!* هنرمند از حمایتتان باخبر شد. 🎶")


@router.callback_query(ArtistReviewCB.filter())
async def review_artist(callback: CallbackQuery, callback_data: ArtistReviewCB) -> None:
    if str(callback.from_user.id) != app_settings.bot_admin_chat_id:
        await callback.answer("⛔️ فقط ادمین می‌تواند هنرمندان را تأیید کند.", show_alert=True)
        return
    status = "approved" if callback_data.approve else "rejected"
    if not crud_donation.set_artist_status(callback_data.artist_id, callback_data.revision, status):
        await callback.answer("ℹ️ این درخواست قبلاً بررسی شده یا هنرمند آن را ویرایش کرده است.",
                              show_alert=True)
        return
    artist = crud_donation.get_artist(callback_data.artist_id)
    bot_username = (await callback.bot.me()).username
    share_link = f"https://t.me/{bot_username}?startapp=artist_{callback_data.artist_id}"
    try:
        await callback.bot.send_message(artist["chat_id"],
                                        format_artist_review_result(callback_data.approve, share_link))
    except Exception:
        logger.error(f"Can't notify artist id={callback_data.artist_id} about review",exc_info=True)
    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    await callback.answer("✅ تأیید شد." if callback_data.approve else "❌ رد شد.", show_alert=True)
