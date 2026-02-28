"""Result types for the decision engine."""

from dataclasses import dataclass, field
from enum import Enum


class Outcome(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    ESCALATE = "escalate"


@dataclass
class CheckResult:
    name: str
    outcome: Outcome
    reason: str
    risk_contribution: float = 0.0  # 0.0–1.0. Only meaningful for soft checks.


@dataclass
class Decision:
    outcome: Outcome
    reason: str
    risk_score: float
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.outcome == Outcome.ALLOW

    @property
    def blocked(self) -> bool:
        return self.outcome == Outcome.BLOCK

    @property
    def escalated(self) -> bool:
        return self.outcome == Outcome.ESCALATE
