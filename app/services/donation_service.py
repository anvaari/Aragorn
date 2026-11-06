"""Artist claims and donations: Telegram Stars, GRAM (via TON Connect) and USDC on Base.

Stars land in the bot's balance and are settled with artists by the admin; GRAM and
USDC go straight from the donor's wallet to the artist's, and are only verified here.
"""
import time
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException

from core.config import app_settings
from db import crud_donation
from log.logger import get_app_logger
from models.donation import ArtistClaim
from payments import ton, usdc
from telegram.bot import create_stars_invoice_link, send_text_to_chat
from telegram_bot.cards import format_artist_claim, format_donation_received
from telegram_bot.keyboards import artist_review_keyboard

logger = get_app_logger(__name__)

ASSET_DECIMALS = {"XTR": 0, "GRAM": 9, "USDC": 6}
# TON Connect requests expire after 600s, so an hour covers slow confirmations; older intents are abandoned.
_GRAM_PENDING_WINDOW = timedelta(hours=1)
_GRAM_PENDING_PER_DONOR = 5  # open intents per donor in that window, so one user can't starve the sweep

def human_amount(asset: str, amount: int) -> str:
    """Base units -> display string, e.g. ('GRAM', 1500000000) -> '1.5'."""
    return f"{Decimal(amount).scaleb(-ASSET_DECIMALS[asset]).normalize():f}"

def public_artist(artist: dict) -> dict:
    """What donors may see: no Telegram ids."""
    return {k: artist[k] for k in ("id", "name", "bio", "ton_address", "evm_address")}

def artist_totals(artist_id: int) -> list[dict]:
    return [{"asset": row["asset"], "amount": human_amount(row["asset"], row["amount"]), "count": row["count"]}
            for row in crud_donation.get_artist_totals(artist_id)]

def _send(chat_id: int | str, text: str, reply_markup: str | None = None) -> None:
    """Best-effort DM: a failed notification must not fail a payment that already succeeded."""
    try:
        status, res = send_text_to_chat(chat_id, text, reply_markup=reply_markup)
    except Exception:
        logger.error(f"Can't send DM to chat_id={chat_id}",exc_info=True)
        return
    if status != 200 or not res.get("ok"):
        logger.error(f"DM to chat_id={chat_id} failed status={status} res={res}")

def _notify_artist(artist: dict, asset: str, amount: int) -> None:
    _send(artist["chat_id"], format_donation_received(asset, human_amount(asset, amount)))

def submit_artist_claim(chat_id: int, username: str | None, claim: ArtistClaim) -> dict:
    if claim.ton_address and not ton.is_valid_address(claim.ton_address):
        raise HTTPException(400, "آدرس کیف پول GRAM (TON) معتبر نیست.")
    if claim.evm_address and not usdc.is_valid_address(claim.evm_address):
        raise HTTPException(400, "آدرس کیف پول شبکه Base معتبر نیست.")
    artist = crud_donation.upsert_artist(chat_id, username, claim.name, claim.bio,
                                         claim.ton_address, claim.evm_address)
    if artist is None:
        raise HTTPException(500, "ثبت پروفایل ناموفق بود.")
    if app_settings.bot_admin_chat_id:
        keyboard = artist_review_keyboard(artist["id"], artist["revision"])
        _send(app_settings.bot_admin_chat_id, format_artist_claim(artist),
              reply_markup=keyboard.model_dump_json(exclude_none=True))
    else:
        logger.warning(f"bot_admin_chat_id is empty; artist id={artist['id']} stays pending")
    return artist

def create_stars_invoice(artist: dict, amount: int) -> str:
    status, res = create_stars_invoice_link(
        title=f"حمایت از {artist['name']}"[:32],
        description=f"{amount} استارز برای {artist['name']} از طریق آرگورن"[:255],
        payload=f"artist:{artist['id']}",
        amount=amount,
    )
    if status != 200 or not res.get("ok"):
        logger.error(f"createInvoiceLink failed status={status} res={res}")
        raise HTTPException(502, "ساخت فاکتور استارز ناموفق بود.")
    return res["result"]

def record_stars_donation(artist_id: int, donor_chat_id: int, amount: int, charge_id: str) -> None:
    """Called on successful_payment; charge_id is unique, so a redelivered update is a no-op."""
    if crud_donation.add_donation(artist_id, donor_chat_id, "XTR", amount, charge_id,
                                  status="confirmed") is None:
        logger.error(f"Stars payment not recorded (duplicate or DB error) charge_id={charge_id}")
        return
    artist = crud_donation.get_artist(artist_id)
    if artist:
        _notify_artist(artist, "XTR", amount)

def _gram_comment(donation_id: int) -> str:
    return f"Aragorn donation #{donation_id}"

def create_gram_donation(artist: dict, donor_chat_id: int, amount: Decimal) -> dict:
    """Open a pending donation and return the TON Connect message that pays it."""
    if not artist["ton_address"]:
        raise HTTPException(400, "این هنرمند کیف پول GRAM ثبت نکرده است.")
    since = (datetime.now() - _GRAM_PENDING_WINDOW).strftime("%Y-%m-%d %H:%M:%S")
    if crud_donation.count_pending_donations(donor_chat_id, "GRAM", since) >= _GRAM_PENDING_PER_DONOR:
        raise HTTPException(429, "چند پرداخت GRAM نیمه‌کاره دارید؛ کمی بعد دوباره امتحان کنید.")
    # Pending rows keep the intended amount (totals only count confirmed rows); confirm overwrites it.
    nano_amount = int(amount.scaleb(ASSET_DECIMALS["GRAM"]))
    donation_id = crud_donation.add_donation(artist["id"], donor_chat_id, "GRAM", amount=nano_amount)
    if donation_id is None:
        raise HTTPException(500, "ثبت حمایت ناموفق بود.")
    return {
        "donation_id": donation_id,
        "address": artist["ton_address"],
        "amount": str(nano_amount),
        "payload": ton.comment_payload(_gram_comment(donation_id)),
    }

def verify_gram_donation(donation: dict) -> str:
    """Look the payment up on-chain by its comment; returns the donation's status."""
    if donation["status"] != "pending":
        return donation["status"]
    artist = crud_donation.get_artist(donation["artist_id"])
    if not artist or not artist["ton_address"]:
        return "pending"
    # 60s margin for clock skew between this host and the chain
    since = int(datetime.strptime(donation["created_at"], "%Y-%m-%d %H:%M:%S").timestamp()) - 60
    found = ton.find_incoming_comment(artist["ton_address"], _gram_comment(donation["id"]), since,
                                      min_value=donation["amount"] or 0)
    if found is None:
        return "pending"
    tx_hash, value = found
    if crud_donation.confirm_donation(donation["id"], value, tx_hash):
        _notify_artist(artist, "GRAM", value)
    return (crud_donation.get_donation(donation["id"]) or donation)["status"]

def verify_pending_gram_donations() -> None:
    """Scheduler sweep: catch payments whose donor closed the Mini App before it confirmed."""
    since = (datetime.now() - _GRAM_PENDING_WINDOW).strftime("%Y-%m-%d %H:%M:%S")
    for donation in crud_donation.get_pending_donations("GRAM", since):
        try:
            verify_gram_donation(donation)
        except Exception:
            logger.error(f"Can't verify pending GRAM donation id={donation['id']}",exc_info=True)
        time.sleep(1)  # keyless toncenter allows ~1 request/second

def record_usdc_donation(artist: dict, donor_chat_id: int, tx_hash: str) -> dict:
    if not artist["evm_address"]:
        raise HTTPException(400, "این هنرمند کیف پول USDC ثبت نکرده است.")
    amount = usdc.transferred_amount(tx_hash, artist["evm_address"])
    if not amount:
        raise HTTPException(400, "انتقال USDC به این هنرمند در این تراکنش پیدا نشد "
                                 "(یا هنوز تأیید نشده است؛ کمی بعد دوباره امتحان کنید).")
    if crud_donation.add_donation(artist["id"], donor_chat_id, "USDC", amount, tx_hash.lower(),
                                  status="confirmed") is None:
        raise HTTPException(409, "این تراکنش قبلاً ثبت شده است.")
    _notify_artist(artist, "USDC", amount)
    return {"status": "confirmed", "amount": human_amount("USDC", amount)}
