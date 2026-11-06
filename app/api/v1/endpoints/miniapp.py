"""JSON API behind the donations Mini App (app/miniapp/index.html)."""
from datetime import datetime, timedelta, timezone

from aiogram.utils.web_app import WebAppUser, safe_parse_webapp_init_data
from fastapi import APIRouter, Depends, Header, HTTPException

from core.config import app_settings
from db import crud_donation
from models.donation import ArtistClaim, GramDonation, StarsDonation, UsdcDonation
from services import donation_service

router = APIRouter()

_INIT_DATA_MAX_AGE = timedelta(hours=24)

def verify_init_data(authorization: str = Header(default="")) -> WebAppUser:
    """Mini App auth: 'Authorization: tma <Telegram.WebApp.initData>', signed with our bot token."""
    scheme, _, init_data = authorization.partition(" ")
    try:
        data = safe_parse_webapp_init_data(app_settings.telegram_bot_token, init_data)
    except ValueError:
        raise HTTPException(401, "Invalid init data")
    if (scheme.lower() != "tma" or data.user is None
            or datetime.now(timezone.utc) - data.auth_date > _INIT_DATA_MAX_AGE):
        raise HTTPException(401, "Invalid init data")
    return data.user

def _approved_artist(artist_id: int) -> dict:
    artist = crud_donation.get_artist(artist_id)
    if not artist or artist["status"] != "approved":
        raise HTTPException(404, "هنرمند پیدا نشد.")
    return artist


@router.get("/tonconnect-manifest.json")
def tonconnect_manifest():
    # Public on purpose: wallets fetch it to show who is asking to connect.
    base = app_settings.miniapp_url.rstrip("/")
    return {"url": base, "name": "Aragorn", "iconUrl": f"{base}/icon.png"}

@router.get("/artists")
def list_artists(user: WebAppUser = Depends(verify_init_data)):
    return [donation_service.public_artist(a) for a in crud_donation.get_approved_artists()]

@router.get("/me")
def my_artist_profile(user: WebAppUser = Depends(verify_init_data)):
    artist = crud_donation.get_artist_by_chat(user.id)
    totals = donation_service.artist_totals(artist["id"]) if artist else []
    return {"artist": artist, "totals": totals}

@router.post("/me")
def claim_artist_profile(claim: ArtistClaim, user: WebAppUser = Depends(verify_init_data)):
    return donation_service.submit_artist_claim(user.id, user.username, claim)

@router.post("/artists/{artist_id}/stars")
def donate_stars(artist_id: int, body: StarsDonation, user: WebAppUser = Depends(verify_init_data)):
    return {"invoice_link": donation_service.create_stars_invoice(_approved_artist(artist_id), body.amount)}

@router.post("/artists/{artist_id}/gram")
def donate_gram(artist_id: int, body: GramDonation, user: WebAppUser = Depends(verify_init_data)):
    return donation_service.create_gram_donation(_approved_artist(artist_id), user.id, body.amount)

@router.post("/donations/{donation_id}/verify")
def verify_gram_donation(donation_id: int, user: WebAppUser = Depends(verify_init_data)):
    donation = crud_donation.get_donation(donation_id)
    if not donation or donation["donor_chat_id"] != user.id:
        raise HTTPException(404, "حمایت پیدا نشد.")
    return {"status": donation_service.verify_gram_donation(donation)}

@router.post("/artists/{artist_id}/usdc")
def donate_usdc(artist_id: int, body: UsdcDonation, user: WebAppUser = Depends(verify_init_data)):
    return donation_service.record_usdc_donation(_approved_artist(artist_id), user.id, body.tx_hash)
