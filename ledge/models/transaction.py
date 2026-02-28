"""Normalized transaction — same shape regardless of which protocol executes it."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal

Protocol = Literal["x402", "transfer"]
Network = Literal["base_testnet", "base_mainnet"]
HttpMethod = Literal["GET", "POST"]

_CHAIN_IDS: dict[str, str] = {
    "base_testnet": "eip155:84532",
    "base_mainnet": "eip155:8453",
}

_FACILITATOR_URLS: dict[str, str] = {
    "base_testnet": "https://x402.org/facilitator",
    "base_mainnet": "https://api.cdp.coinbase.com/platform/v2/x402",
}

_USDC_CONTRACTS: dict[str, str] = {
    "eip155:84532": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    "eip155:8453": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
}


@dataclass
class Transaction:
    amount_usd: float
    to: str
    reason: str
    task_id: str
    protocol: Protocol = "x402"
    network: Network = "base_testnet"
    endpoint_url: str | None = None
    endpoint_method: HttpMethod = "GET"
    endpoint_json: dict[str, Any] | None = None
    token: str = "USDC"
    data: str = "0x"
    chain_id: str = ""
    facilitator_url: str = ""

    def __post_init__(self) -> None:
        self.chain_id = _CHAIN_IDS[self.network]
        self.facilitator_url = (
            os.environ.get("X402_FACILITATOR_URL") or _FACILITATOR_URLS[self.network]
        )

    @property
    def amount_atomic(self) -> int:
        return int(self.amount_usd * 1_000_000)

    @property
    def usdc_contract(self) -> str:
        return _USDC_CONTRACTS.get(self.chain_id, "")
