"""
EnvSigner — reads private key from environment variable, wipes it immediately.

SECURITY:
  1. Key read from os.environ exactly once in __init__
  2. Deleted from os.environ immediately after reading (in finally block)
  3. Stored only in eth_account LocalAccount — no method to export raw key
  4. Raw key string overwritten before local variable goes out of scope
  5. repr() never contains key material

FOR DEVELOPMENT ONLY.
In production: use TurnkeySigner or AwsKmsSigner (see docs/SIGNING.md).
"""

from __future__ import annotations

import json
import os

from eth_account import Account
from eth_account.messages import encode_defunct, encode_typed_data

from ledge.errors import SigningFailed
from ledge.signing._secure_account import _SecureAccountWrapper
from ledge.signing.base import SigningProvider


def _domain_to_eip712(domain: dict[str, object]) -> dict[str, object]:
    """Convert domain (snake_case from x402) to EIP-712 camelCase."""
    out: dict[str, object] = {}
    for k, v in domain.items():
        if k == "chain_id":
            out["chainId"] = v
        elif k == "verifying_contract":
            out["verifyingContract"] = v
        else:
            out[k] = v
    return out


class EnvSigner(SigningProvider):
    def __init__(self, env_var: str = "AGENT_PRIVATE_KEY") -> None:
        raw_key: str | None = os.environ.get(env_var)
        try:
            if not raw_key:
                raise ValueError(
                    f"'{env_var}' not set. Copy .env.example to .env and set your key."
                )
            try:
                account = Account.from_key(raw_key)
                self._account = _SecureAccountWrapper(account)
            except Exception as e:
                raise ValueError(f"Invalid private key in '{env_var}'") from e
        finally:
            # CRITICAL: always remove from env, even if from_key() raised
            os.environ.pop(env_var, None)
            if raw_key:
                # Overwrite the local string before it goes out of scope
                raw_key = "0" * len(raw_key)
            del raw_key

    def sign(self, tx: dict[str, object]) -> str:
        """Sign an EIP-1559 transaction dict. Returns raw signed hex."""
        try:
            signed = self._account.sign_transaction(tx)
            raw = signed.raw_transaction.hex()
            return raw if raw.startswith("0x") else f"0x{raw}"
        except Exception as e:
            raise SigningFailed("Transaction signing failed") from e

    def sign_typed_data(
        self,
        domain: dict[str, object],
        types: dict[str, object],
        message: dict[str, object],
        primary_type: str | None = None,
    ) -> str:
        """
        Sign EIP-712 typed data. Used by X402Executor for payment authorization.

        When primary_type is provided, uses eth_account encode_typed_data for
        correct EIP-712 struct hash. Otherwise signs JSON (for tests only).
        """
        try:
            if primary_type:
                # EIP-712: domain must use camelCase for encode_typed_data
                domain_eip712 = _domain_to_eip712(domain)
                full_message = {
                    "types": types,
                    "primaryType": primary_type,
                    "domain": domain_eip712,
                    "message": message,
                }
                signable = encode_typed_data(full_message=full_message)
            else:
                # Fallback for tests: sign JSON string
                payload = {"domain": domain, "types": types, "message": message}
                signable = encode_defunct(text=json.dumps(payload, sort_keys=True))
            signed = self._account.sign_message(signable)
            raw = signed.signature.hex()
            return raw if raw.startswith("0x") else f"0x{raw}"
        except Exception as e:
            raise SigningFailed("EIP-712 signing failed") from e

    @property
    def address(self) -> str:
        return str(self._account.address)

    def __repr__(self) -> str:
        # NEVER include key material in repr
        return f"EnvSigner(address={self.address})"
