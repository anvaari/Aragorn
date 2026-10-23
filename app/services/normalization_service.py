from db import crud_artist, crud_proposals
from log.logger import get_app_logger
from open_ai.artist_search import normalize_artist_names

logger = get_app_logger(__name__)

_NORMALIZE_CHUNK = 25  # names per LLM call


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def propose_normalizations(limit: int = 100) -> dict:
    """Create pending Persian->English name proposals for admin review.

    Artists that already have a normalized_name or a pending proposal are
    skipped (see crud_artist.get_artists_missing_normalized_name); junk names
    come back empty from the LLM and are silently dropped.
    """
    candidates = crud_artist.get_artists_missing_normalized_name(limit)
    proposed = skipped = 0
    for chunk in _chunks(candidates, _NORMALIZE_CHUNK):
        mapping = normalize_artist_names([c["name"] for c in chunk])
        if mapping is None:
            continue  # LLM failure — the same artists are retried next run
        for candidate in chunk:
            english = mapping.get(candidate["name"], "")
            if not english:
                skipped += 1
                continue
            if crud_proposals.create_proposal(candidate["id"], candidate["name"], english) is not None:
                proposed += 1
    logger.info(f"Normalization proposals: {proposed} created, {skipped} junk, "
                f"{len(candidates)} candidates")
    return {"candidates": len(candidates), "proposed": proposed, "skipped": skipped}


def apply_proposal(proposal_id: int, approve: bool) -> dict | None:
    """Decide one proposal; returns the (updated) proposal for re-rendering."""
    proposal = crud_proposals.get_proposal(proposal_id)
    if not proposal or proposal["status"] != "pending":
        return proposal
    if approve:
        crud_proposals.approve_proposal(proposal_id)
        logger.info(f"Normalization approved: artist {proposal['artist_id']} "
                    f"{proposal['current_name']!r} -> {proposal['proposed_name']!r}")
    else:
        crud_proposals.set_proposal_status(proposal_id, "rejected")
    return crud_proposals.get_proposal(proposal_id)


def apply_normalizations_directly(limit: int = 100) -> dict:
    """CLI-only: write normalized_name without the Telegram review step."""
    candidates = crud_artist.get_artists_missing_normalized_name(limit)
    applied = skipped = 0
    for chunk in _chunks(candidates, _NORMALIZE_CHUNK):
        mapping = normalize_artist_names([c["name"] for c in chunk])
        if mapping is None:
            continue
        for candidate in chunk:
            english = mapping.get(candidate["name"], "")
            if not english:
                skipped += 1
                continue
            crud_artist.set_normalized_name(candidate["id"], english)
            applied += 1
            logger.info(f"Normalization applied: artist {candidate['id']} "
                        f"{candidate['name']!r} -> {english!r}")
    return {"candidates": len(candidates), "applied": applied, "skipped": skipped}


def notify_admin_proposals(pending_count: int) -> bool:
    """DM the admin one review entry-point; False when disabled or send failed."""
    from core.config import app_settings
    from telegram.bot import send_text_to_chat
    from telegram_bot.callbacks import NormPageCB
    from telegram_bot.keyboards import normalization_notify_keyboard

    chat_id = app_settings.bot_admin_chat_id.strip()
    if not chat_id:
        logger.warning("bot_admin_chat_id is empty; normalization review "
                       "notification skipped")
        return False
    text = (f"🛠 *{pending_count} پیشنهاد اصلاح نام هنرمند* در انتظار بررسی شماست.\n\n"
            "_نام اصلی هنرمند تغییر نمی‌کند؛ تأیید شما نام انگلیسی را در ستون "
            "جداگانه‌ای ذخیره می‌کند._")
    markup = normalization_notify_keyboard()
    try:
        status, _ = send_text_to_chat(chat_id, text, markup.model_dump_json())
    except Exception:
        logger.error(f"Can't notify admin (chat_id={chat_id}) about proposals",exc_info=True)
        return False
    if not (200 <= status < 300):
        logger.warning(f"Admin notification returned HTTP {status}")
        return False
    return True
