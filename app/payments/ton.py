"""GRAM (TON's native coin, formerly Toncoin) helpers: address check, comment payload, payment lookup."""
import base64
import binascii

import requests

from log.logger import get_app_logger
from telegram.bot import _proxies

logger = get_app_logger(__name__)

TONCENTER_API = "https://toncenter.com/api/v3"

def is_valid_address(address: str) -> bool:
    """Mainnet user-friendly address (EQ…/UQ…, 48 chars) with a valid CRC16 checksum."""
    if len(address) != 48:
        return False
    try:
        raw = base64.urlsafe_b64decode(address.replace("+", "-").replace("/", "_"))
    except (ValueError, binascii.Error):
        return False
    # byte 0 = flags (0x80 marks testnet-only), 1 = workchain, 2..33 = hash, 34..35 = CRC16-XMODEM
    return (len(raw) == 36 and not raw[0] & 0x80
            and binascii.crc_hqx(raw[:34], 0).to_bytes(2, "big") == raw[34:])

def comment_payload(text: str) -> str:
    """Base64 BOC of a text-comment cell (32-bit zero opcode + UTF-8), for TON Connect's payload."""
    data = bytes(4) + text.encode()
    if len(data) > 127:
        raise ValueError("comment must fit in a single cell (123 bytes)")
    cell = bytes([0, 2 * len(data)]) + data  # descriptors: no refs, whole bytes (no completion tag)
    # magic, size_bytes=1 (no index/crc), off_bytes=1, cells=1, roots=1, absent=0, cells size, root=0
    boc = bytes.fromhex("b5ee9c72") + bytes([1, 1, 1, 1, 0, len(cell), 0]) + cell
    return base64.b64encode(boc).decode()

def find_incoming_comment(address: str, comment: str, since_utime: int,
                          min_value: int = 0) -> tuple[str, int] | None:
    """(tx hash, nanoGRAM) of a successful incoming transfer of >= min_value carrying comment, or None."""
    try:
        # oldest first: the payment lands right after since_utime, so it is on the first page.
        # shortcut: only 100 txs are scanned; paginate if an artist uses a very busy (exchange) wallet

        res = requests.get(
            f"{TONCENTER_API}/transactions",
            params={"account": address, "start_utime": since_utime, "limit": 100, "sort": "asc"},
            proxies=_proxies(),
            timeout=10,
        )
        res.raise_for_status()
        transactions = res.json().get("transactions", [])
    except (requests.RequestException, ValueError):
        # shortcut: keyless toncenter allows ~1 rps, so 429s land here; add an API key if it gets busy
        logger.warning(f"toncenter lookup failed for {address}",exc_info=True)
        return None
    for tx in transactions:
        msg = tx.get("in_msg") or {}
        decoded = (msg.get("message_content") or {}).get("decoded") or {}
        # aborted = bounced back (e.g. bounceable transfer to an uninitialized wallet); unknown counts as aborted.
        # min_value stops a dust tx with a copied comment from consuming someone's donation.
        if (msg.get("source") and decoded.get("comment") == comment
                and not (tx.get("description") or {}).get("aborted", True)
                and int(msg["value"]) >= min_value):
            return tx["hash"], int(msg["value"])
    return None
