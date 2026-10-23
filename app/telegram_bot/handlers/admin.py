import math

from aiogram import Router
from aiogram.types import CallbackQuery

from core.config import app_settings
from db import crud_proposals
from log.logger import get_app_logger
from services.normalization_service import apply_proposal
from telegram_bot.callbacks import NormBulkCB, NormDecisionCB, NormPageCB
from telegram_bot.cards import _escape_md
from telegram_bot.handlers.common import safe_edit
from telegram_bot.keyboards import normalization_review_keyboard

logger = get_app_logger(__name__)

router = Router()

_PAGE_SIZE = 10

_DENIED_TEXT = "⛔ این بخش فقط برای مدیر ربات است."
_EMPTY_TEXT = "✅ پیشنهاد در انتظاری وجود ندارد. آفرین!"

def _is_admin(callback: CallbackQuery) -> bool:
    admin_id = app_settings.bot_admin_chat_id.strip()
    return bool(admin_id) and str(callback.from_user.id) == admin_id

def _review_page(page: int) -> tuple[str, object] | None:
    """(text, markup) for one review page, or None when nothing is pending."""
    total = crud_proposals.count_pending()
    if total == 0:
        return None
    pages = max(1, math.ceil(total / _PAGE_SIZE))
    page = max(0, min(page, pages - 1))
    proposals = crud_proposals.get_pending_proposals(limit=_PAGE_SIZE, offset=page * _PAGE_SIZE)
    lines = [f"🛠 *پیشنهاد اصلاح نام هنرمند* — {total} مورد در انتظار:", ""]
    for proposal in proposals:
        lines.append(f"#{proposal['id']} — {_escape_md(proposal['current_name'])} → "
                     f"{_escape_md(proposal['proposed_name'])}")
    lines.append("")
    lines.append("_تأیید = ذخیره‌ی نام انگلیسی در ستون جداگانه؛ نام اصلی دست‌نخورده می‌ماند._")
    return "\n".join(lines), normalization_review_keyboard(
        proposals, page, has_prev=page > 0, has_next=page < pages - 1)

async def _show_page(callback: CallbackQuery, page: int) -> None:
    rendered = _review_page(page)
    if rendered is None:
        await safe_edit(callback, _EMPTY_TEXT, None)
        return
    text, markup = rendered
    await safe_edit(callback, text, markup)

@router.callback_query(NormPageCB.filter())
async def norm_page(callback: CallbackQuery, callback_data: NormPageCB) -> None:
    if not _is_admin(callback):
        await callback.answer(_DENIED_TEXT, show_alert=True)
        return
    await _show_page(callback, callback_data.page)
    await callback.answer()

@router.callback_query(NormDecisionCB.filter())
async def norm_decision(callback: CallbackQuery, callback_data: NormDecisionCB) -> None:
    if not _is_admin(callback):
        await callback.answer(_DENIED_TEXT, show_alert=True)
        return
    approved = bool(callback_data.approve)
    apply_proposal(callback_data.proposal_id, approved)
    await _show_page(callback, callback_data.page)
    await callback.answer("✅ تأیید شد" if approved else "❌ رد شد")

@router.callback_query(NormBulkCB.filter())
async def norm_bulk(callback: CallbackQuery, callback_data: NormBulkCB) -> None:
    if not _is_admin(callback):
        await callback.answer(_DENIED_TEXT, show_alert=True)
        return
    if callback_data.scope == "page":
        targets = crud_proposals.get_pending_proposals(limit=_PAGE_SIZE,
                                                       offset=callback_data.page * _PAGE_SIZE)
    else:
        targets = crud_proposals.get_pending_proposals(limit=10_000)
    for proposal in targets:
        apply_proposal(proposal["id"], True)
    await _show_page(callback, callback_data.page)
    await callback.answer(f"✅ {len(targets)} پیشنهاد تأیید شد")
