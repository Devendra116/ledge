"""Append-only JSONL audit log. One JSON object per line.

Every transaction attempt is logged — ALLOW, BLOCK, and ESCALATE.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid runtime circular imports
    from ledge.engine.result import Decision
    from ledge.models import Transaction


@dataclass
class AuditEvent:
    event_id: str
    timestamp: str  # ISO 8601 UTC
    agent_id: str
    task_id: str
    task_description: str
    protocol: str  # "x402" | "transfer"
    network: str  # "base_testnet" | "base_mainnet"
    outcome: str  # "allow" | "block" | "escalate"
    amount_usd: float
    to: str
    reason_given: str
    decision_reason: str
    risk_score: float
    tx_hash: str | None
    checks_run: list[dict[str, object]]


class AuditLogger:
    """
    JSONL logger. One event per line. Append-only. Never truncates.
    JSONL is readable with any text editor, greppable, parseable line-by-line.
    """

    def __init__(self, log_path: str = "./ledge_audit.jsonl") -> None:
        self._path = log_path

    def log(self, event: AuditEvent) -> None:
        """Append a single event. Thread-safe via append mode."""
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), default=str) + "\n")

    def recent(self, n: int = 20) -> list[AuditEvent]:
        """Return last n events without loading entire file into memory."""
        try:
            with open(self._path, encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            return []

        events: list[AuditEvent] = []
        for line in lines[-n:]:
            line = line.strip()
            if not line:
                continue
            events.append(AuditEvent(**json.loads(line)))
        return events


def make_audit_event(
    agent_id: str,
    task_id: str,
    task_description: str,
    tx: Transaction,
    decision: Decision,
    tx_hash: str | None,
) -> AuditEvent:
    """Factory. Called by Wallet after every pay() attempt regardless of outcome."""
    return AuditEvent(
        event_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        agent_id=agent_id,
        task_id=task_id,
        task_description=task_description,
        protocol=tx.protocol,
        network=tx.network,
        outcome=decision.outcome.value,
        amount_usd=tx.amount_usd,
        to=tx.to,
        reason_given=tx.reason,
        decision_reason=decision.reason,
        risk_score=decision.risk_score,
        tx_hash=tx_hash,
        checks_run=[
            {
                "name": c.name,
                "outcome": c.outcome.value,
                "reason": c.reason,
                "risk": c.risk_contribution,
            }
            for c in decision.checks
        ],
    )
