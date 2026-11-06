"""JSON API behind the Mini App (app/miniapp/index.html): events, reminders, artist donations."""
import re
from datetime import datetime, timedelta, timezone

from aiogram.utils.web_app import WebAppUser, safe_parse_webapp_init_data
from fastapi import APIRouter, Depends, Header, HTTPException

from core.config import app_settings
from db import crud_bot, crud_donation
from db.crud_event import get_events_by_jdate_with_ids
from models.donation import ArtistClaim, GramDonation, StarsDonation, UsdcDonation
from models.event import EventCreate, EventReminder
from services import donation_service, reminder_service
from telegram.event_formatter import LOC_PATTERN
from utils.event_time import format_jdatetime, jdate_fa, jdate_for_offset

_DAYS_AHEAD = 7  # the day strip on the Mini App's home screen

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

def _event_json(event_id: int, event: EventCreate, reminded: set[int], artists: list[dict]) -> dict:
    try:
        calendar_link = event.google_calendar_link
    except ValueError:  # datetime the Shamsi parser rejects
        calendar_link = ""
    is_coords = bool(re.match(LOC_PATTERN, event.location))
    return {
        "id": event_id, **event.model_dump(),
        "google_calendar_link": calendar_link,
        "maps_link": f"https://www.google.com/maps?q={event.location}" if is_coords else "",
        "reminded": event_id in reminded,
        # shortcut: name-in-performers match can link the wrong artist for very short names; store artist ids on events to fix
        "artist_id": next((a["id"] for a in artists if a["name"] in event.performers), None),
    }


@router.get("/tonconnect-manifest.json")
def tonconnect_manifest():
    # Public on purpose: wallets fetch it to show who is asking to connect.
    base = app_settings.miniapp_url.rstrip("/")
    return {"url": base, "name": "Aragorn", "iconUrl": f"{base}/icon.png"}

@router.get("/events")
def upcoming_events(user: WebAppUser = Depends(verify_init_data)):
    """Today and the next six days (Shamsi), each with its events."""
    reminded = {r["event_id"] for r in crud_bot.get_user_reminders(user.id)}
    artists = crud_donation.get_approved_artists()
    days = []
    for offset in range(_DAYS_AHEAD):
        jdate, weekday = jdate_for_offset(offset)
        days.append({"jdate": jdate, "weekday": weekday, "date_fa": jdate_fa(jdate), "events": [
            _event_json(event_id, event, reminded, artists)
            for event_id, event in get_events_by_jdate_with_ids(jdate)]})
    return days

@router.post("/events/{event_id}/reminders")
def set_event_reminder(event_id: int, body: EventReminder, user: WebAppUser = Depends(verify_init_data)):
    try:
        return {"created": reminder_service.set_event_reminders(user.id, event_id, body.hours)}
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.get("/reminders")
def my_reminders(user: WebAppUser = Depends(verify_init_data)):
    return [{"id": r["id"], "event_id": r["event_id"], "title": r["event_title"] or "رویداد",
             "when": format_jdatetime(r["event_datetime"]), "location": r["event_location"] or "",
             "hours": reminder_service.hours_before(r["event_datetime"], r["remind_at"])}
            for r in crud_bot.get_user_reminders(user.id)]

@router.delete("/reminders/{reminder_id}")
def delete_my_reminder(reminder_id: int, user: WebAppUser = Depends(verify_init_data)):
    if not crud_bot.delete_reminder(reminder_id, user.id):
        raise HTTPException(404, "یادآوری پیدا نشد.")
    return {"deleted": True}

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
