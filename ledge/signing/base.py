"""Abstract signing interface. Two methods: one for on-chain tx, one for EIP-712."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SigningProvider(ABC):
    """
    All signing backends implement this interface.
    The decision engine never sees this class.
    Only the executor calls it, after the engine has approved.
    """

    @abstractmethod
    def sign(self, tx: dict[str, Any]) -> str:
        """
        Sign an on-chain transaction dict (EIP-1559 format).
        Returns raw signed transaction hex string.
        Used by: TransferExecutor.
        """
        ...

    @abstractmethod
    def sign_typed_data(
        self,
        domain: dict[str, Any],
        types: dict[str, Any],
        message: dict[str, Any],
        primary_type: str | None = None,
    ) -> str:
        """
        Sign EIP-712 typed structured data.
        Returns hex signature string.
        If primary_type is provided, signers should use proper EIP-712 encoding.
        Used by: X402Executor (x402 uses EIP-712 for payment authorization).
        """
        ...

    @property
    @abstractmethod
    def address(self) -> str:
        """Public address. Safe to expose. Used by executors to build payment payloads."""
        ...
