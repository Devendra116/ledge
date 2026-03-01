"""Abstract payment executor and shared result type."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ledge.models.transaction import Transaction
from ledge.signing.base import SigningProvider


@dataclass
class ExecutionResult:
    """Returned by every executor on success."""

    tx_hash: str
    protocol: str
    network: str
    amount: float
    response_data: dict[str, object] | None = None


class PaymentExecutor(ABC):
    """
    Protocol-specific payment executor.
    Only called after the decision engine returns ALLOW.
    Never makes policy decisions — only executes.

    To add a new protocol: subclass this, implement execute().
    No other files need to change.
    """

    @abstractmethod
    def execute(self, tx: Transaction, signer: SigningProvider) -> ExecutionResult:
        """
        Execute the approved transaction.
        Raises ExecutionFailed on any failure.
        Must NOT be called before the decision engine approves.
        """
        ...
