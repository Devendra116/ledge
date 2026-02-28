"""MockSigner — no real keys, no network. For tests and demos only."""

from __future__ import annotations

from typing import Any

from ledge.signing.base import SigningProvider


class MockSigner(SigningProvider):
    """
    Returns deterministic fake signatures. Safe to use with any data.
    Never connects to any network.
    """

    def __init__(
        self,
        mock_address: str = "0xMockAddress1234567890AbCdEf1234567890Ab",
    ) -> None:
        self._address = mock_address

    def sign(self, tx: dict[str, Any]) -> str:
        value = tx.get("value", 0)
        to = str(tx.get("to", "unknown"))[:10]
        return f"0xMOCK_TX_{to}_{value}"

    def sign_typed_data(
        self,
        domain: dict[str, Any],
        types: dict[str, Any],
        message: dict[str, Any],
        primary_type: str | None = None,
    ) -> str:
        amount = message.get("value", message.get("amount", "unknown"))
        return f"0xMOCK_EIP712_{amount}"

    @property
    def address(self) -> str:
        return self._address

    def __repr__(self) -> str:
        return f"MockSigner(address={self._address})"
