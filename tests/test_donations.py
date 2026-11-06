"""Self-checks for the artist donations Mini App (payments, auth, ledger).

Run from the repo root, no network or real tokens needed:
    python tests/test_donations.py      (pytest works too)
"""
import hashlib
import hmac
import json
import os
import sys
import tempfile
import time
from urllib.parse import urlencode

_TOKEN = "123456:TEST-TOKEN"
for key, value in {
    "telegram_bot_tk": _TOKEN, "telegram_chat": "0", "openai_api_k": "x", "openai_text_model": "x",
    "openai_image_model": "x", "instagram_login_session_file": "x", "aragorn_tk": "x",
    "tg_gpt_ig_proxy": "", "log_level": "WARNING",
    "database_file_path": os.path.join(tempfile.mkdtemp(), "test.sqlite"),
}.items():
    os.environ[key] = value
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from types import SimpleNamespace  # noqa: E402

from fastapi import HTTPException  # noqa: E402

from api.v1.endpoints.miniapp import verify_init_data  # noqa: E402
from core.config import app_settings  # noqa: E402
from db import crud_donation  # noqa: E402
from payments import ton, usdc  # noqa: E402
from services import donation_service  # noqa: E402
from services.donation_service import human_amount  # noqa: E402
from telegram_bot.keyboards import main_menu_keyboard  # noqa: E402

_TON_ADDRESS = "UQCFJEP4WZ_mpdo0_kMEmsTgvrMHG7K_tWY16pQhKHwoOtFz"
_BASE_ADDRESS = "0x9d7d8b567ee10bcb4f9db438245e1d0668175d72"


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self.payload, self.status_code = payload, status_code

    def json(self) -> dict:
        return self.payload

    def raise_for_status(self) -> None:
        pass


def _signed_init_data(user_id: int = 42, auth_date: int | None = None) -> str:
    fields = {"auth_date": str(auth_date or int(time.time())), "query_id": "AAH",
              "user": json.dumps({"id": user_id, "first_name": "Test"})}
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", _TOKEN.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def _rejected(authorization: str) -> bool:
    try:
        verify_init_data(authorization)
    except HTTPException as e:
        return e.status_code == 401
    return False


def test_comment_payload_matches_ton_core():
    # Reference: @ton/core beginCell().storeUint(0, 32).storeStringTail(text).endCell().toBoc({crc32: false})
    assert ton.comment_payload("Aragorn donation #1") == "te6ccgEBAQEAGQAALgAAAABBcmFnb3JuIGRvbmF0aW9uICMx"


def test_ton_address_check():
    assert ton.is_valid_address(_TON_ADDRESS)
    assert ton.is_valid_address("EQCFJEP4WZ_mpdo0_kMEmsTgvrMHG7K_tWY16pQhKHwoOoy2")  # bounceable form
    assert not ton.is_valid_address(_TON_ADDRESS[:-1] + "a")  # checksum typo
    assert not ton.is_valid_address("kQCFJEP4WZ_mpdo0_kMEmsTgvrMHG7K_tWY16pQhKHwoOjc8")  # testnet-only
    assert not ton.is_valid_address("not an address")


def test_init_data_auth():
    assert verify_init_data("tma " + _signed_init_data(user_id=42)).id == 42
    assert _rejected("tma " + _signed_init_data().replace("42", "43"))  # tampered user
    assert _rejected("tma " + _signed_init_data(auth_date=int(time.time()) - 3 * 86400))  # stale
    assert _rejected("Bearer " + _signed_init_data())
    assert _rejected("")


def test_usdc_amount_from_receipt():
    def log(contract: str, to: str, value: int) -> dict:
        return {"address": contract, "data": hex(value),
                "topics": [usdc._TRANSFER_TOPIC, "0x" + "11" * 32, "0x" + to[2:].rjust(64, "0")]}
    receipt = {"status": "0x1", "logs": [
        log(usdc.USDC_CONTRACT.upper().replace("0X", "0x"), _BASE_ADDRESS, 5_000_000),
        log(usdc.USDC_CONTRACT, "0x" + "22" * 20, 7_000_000),  # someone else
        log("0x" + "33" * 20, _BASE_ADDRESS, 9_000_000),       # not USDC
    ]}
    original = usdc.requests.post
    try:
        usdc.requests.post = lambda *a, **k: _FakeResponse({"result": receipt})
        assert usdc.transferred_amount("0x" + "ab" * 32, _BASE_ADDRESS.upper().replace("0X", "0x")) == 5_000_000
        usdc.requests.post = lambda *a, **k: _FakeResponse({"result": {**receipt, "status": "0x0"}})
        assert usdc.transferred_amount("0x" + "ab" * 32, _BASE_ADDRESS) == 0
    finally:
        usdc.requests.post = original


def test_gram_lookup_matches_comment():
    def tx(tx_hash: str, comment: str, aborted: bool, value: str = "1500000000") -> dict:
        return {"hash": tx_hash, "description": {"aborted": aborted},
                "in_msg": {"source": "0:AB", "value": value,
                           "message_content": {"decoded": {"@type": "text_comment", "comment": comment}}}}
    page = {"transactions": [tx("bounced", "Aragorn donation #7", True),
                             tx("other", "Aragorn donation #8", False),
                             tx("paid", "Aragorn donation #7", False),
                             tx("dust", "Aragorn donation #9", False, value="1")]}
    original = ton.requests.get
    try:
        ton.requests.get = lambda *a, **k: _FakeResponse(page)
        assert ton.find_incoming_comment(_TON_ADDRESS, "Aragorn donation #7", 0) == ("paid", 1_500_000_000)
        assert ton.find_incoming_comment(_TON_ADDRESS, "Aragorn donation #10", 0) is None
        # 1 nanoGRAM with a copied comment must not confirm (and consume) a 2.5 GRAM intent
        assert ton.find_incoming_comment(_TON_ADDRESS, "Aragorn donation #9", 0, min_value=2_500_000_000) is None
    finally:
        ton.requests.get = original


def test_gram_sweep_survives_a_bad_row():
    seen = []
    def failing_verify(donation: dict) -> str:
        seen.append(donation["id"])
        raise KeyError("description")
    originals = (donation_service.verify_gram_donation, donation_service.time,
                 crud_donation.get_pending_donations)
    try:
        donation_service.verify_gram_donation = failing_verify
        donation_service.time = SimpleNamespace(sleep=lambda seconds: None)
        crud_donation.get_pending_donations = lambda asset, since: [{"id": 1}, {"id": 2}]
        donation_service.verify_pending_gram_donations()
        assert seen == [1, 2]
    finally:
        (donation_service.verify_gram_donation, donation_service.time,
         crud_donation.get_pending_donations) = originals


def test_miniapp_button_needs_https():
    def has_web_app_button(url: str) -> bool:
        app_settings.miniapp_url = url
        return any(button.web_app for row in main_menu_keyboard().inline_keyboard for button in row)
    original = app_settings.miniapp_url
    try:
        assert has_web_app_button(" https://aragorn.example.com/miniapp/ ")
        assert not has_web_app_button("http://x")
        assert not has_web_app_button("")
    finally:
        app_settings.miniapp_url = original


def test_claim_review_and_ledger():
    artist = crud_donation.upsert_artist(1001, "artist", "Artist", "", _TON_ADDRESS, "")
    assert (artist["status"], artist["revision"]) == ("pending", 0)
    edited = crud_donation.upsert_artist(1001, "artist", "Famous Artist", "", _TON_ADDRESS, "")
    assert edited["revision"] == 1
    assert not crud_donation.set_artist_status(artist["id"], 0, "approved")  # admin saw the old name
    assert crud_donation.set_artist_status(artist["id"], 1, "approved")

    assert crud_donation.add_donation(artist["id"], 2002, "XTR", 100, "charge-1", "confirmed")
    assert crud_donation.add_donation(artist["id"], 2002, "XTR", 100, "charge-1", "confirmed") is None
    pending_id = crud_donation.add_donation(artist["id"], 2002, "GRAM")
    assert crud_donation.confirm_donation(pending_id, 1_500_000_000, "tx-1")
    assert not crud_donation.confirm_donation(pending_id, 1_500_000_000, "tx-1")  # no double notify
    totals = {t["asset"]: (t["amount"], t["count"]) for t in crud_donation.get_artist_totals(artist["id"])}
    assert totals == {"GRAM": (1_500_000_000, 1), "XTR": (100, 1)}
    assert (human_amount("GRAM", 1_500_000_000), human_amount("XTR", 100), human_amount("USDC", 5_000_000)) \
        == ("1.5", "100", "5")


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print(f"ALL {len(tests)} PASS")
