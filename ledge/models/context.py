"""Task context — passed to every decision engine check."""

import time
from dataclasses import dataclass, field


@dataclass
class TaskContext:
    task_id: str
    task_description: str
    agent_id: str
    budget_allocated: float
    budget_spent: float
    recent_tx_timestamps: list[float] = field(default_factory=list)
    recent_tx_destinations: list[str] = field(default_factory=list)
    historical_amounts_usd: list[float] = field(default_factory=list)

    @property
    def budget_remaining(self) -> float:
        return self.budget_allocated - self.budget_spent

    def record_tx(self, amount_usd: float, destination: str) -> None:
        self.budget_spent += amount_usd
        self.recent_tx_timestamps.append(time.time())
        self.recent_tx_destinations.append(destination)
        self.historical_amounts_usd.append(amount_usd)
