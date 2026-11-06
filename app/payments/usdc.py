"""USDC on Base: address check and on-chain transfer lookup over JSON-RPC."""
import re

import requests

from log.logger import get_app_logger
from telegram.bot import _proxies

logger = get_app_logger(__name__)

BASE_RPC_URL = "https://mainnet.base.org"
USDC_CONTRACT = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"  # Circle-issued USDC on Base
_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"  # Transfer(address,address,uint256)
_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

def is_valid_address(address: str) -> bool:
    return bool(_ADDRESS_RE.match(address))

def transferred_amount(tx_hash: str, to_address: str) -> int:
    """USDC base units (6 decimals) a successful tx sent to to_address; 0 if none or not mined yet."""
    try:
        res = requests.post(
            BASE_RPC_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": "eth_getTransactionReceipt", "params": [tx_hash]},
            proxies=_proxies(),
            timeout=10,
        )
        res.raise_for_status()
        receipt = res.json().get("result")
    except (requests.RequestException, ValueError):
        logger.warning(f"Base RPC lookup failed for {tx_hash}",exc_info=True)
        return 0
    if not receipt or receipt.get("status") != "0x1":
        return 0
    to_topic = "0x" + to_address.lower()[2:].rjust(64, "0")
    return sum(
        int(log["data"], 16) for log in receipt.get("logs", [])
        if log["address"].lower() == USDC_CONTRACT
        and len(log["topics"]) == 3 and log["topics"][0] == _TRANSFER_TOPIC
        and log["topics"][2].lower() == to_topic
    )
