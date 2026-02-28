"""Operator-defined rules."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Policy:
    simulate_before_sign: bool = False
    max_amount_usd_per_tx: float = 10.0
    max_spend_usd_per_task: float = 50.0
    allowed_networks: list[str] = field(default_factory=lambda: ["base_testnet", "base_mainnet"])
    blocked_addresses: list[str] = field(default_factory=list)
    require_reason: bool = True
    min_reason_length: int = 10
    coherence_weight: float = 0.4
    velocity_window_seconds: int = 60
    velocity_max_tx: int = 5
    velocity_weight: float = 0.35
    anomaly_multiplier_threshold: float = 3.0
    anomaly_weight: float = 0.25
    escalate_risk_threshold: float = 0.65


def load_policy(path: str) -> Policy:
    with open(path) as f:
        data: dict[str, Any] = json.load(f)
    known = set(Policy.__dataclass_fields__)
    return Policy(**{k: v for k, v in data.items() if k in known})
