"""
Executor-specific payment params. Each protocol has its own param type.

Add new param types here when adding a new executor; keep protocol-agnostic
code using the PaymentParams union so the wallet and engine stay modular.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union

from ledge.models.transaction import HttpMethod


@dataclass(frozen=True)
class X402Params:
    """Params for x402 (HTTP paid API) execution."""

    url: str
    method: HttpMethod = "GET"
    body: dict[str, object] | None = None


@dataclass(frozen=True)
class TransferParams:
    """Params for on-chain transfer execution. Stub for future use."""

    pass


# Union of all executor param types. Add new variants when adding executors.
PaymentParams = Union[X402Params, TransferParams]

# Protocol literal for type narrowing (matches Protocol in transaction.py).
ProtocolKind = Literal["x402", "transfer"]
