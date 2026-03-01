"""
EncryptedFileSigner — imports an existing Ethereum keystore JSON file; signs with it.

The SDK does NOT create key files. You use a keystore file produced elsewhere (Geth,
MetaMask, Hardhat, or any tool that outputs Ethereum keystore JSON v3). The signer
reads the file, decrypts with passphrase, and uses the key only for signing. The raw
key is never exposed to the agent or to code — no getter, no repr, no logging.

SECURITY:
  - File: standard Ethereum keystore JSON (version 3). Not created by the SDK.
  - Passphrase from env or constructor; env cleared after read when using passphrase_env.
  - Decrypted key used only to build an internal Account; reference dropped, not stored.
  - Only sign() and sign_typed_data() perform signing; address is public. No way to export the key.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

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


def _load_keystore(path: Path) -> dict[str, object]:
    """Read and parse JSON keystore. Raises SigningFailed on invalid file. Messages are generic to avoid leaking content."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise SigningFailed("Cannot read key file") from e
    except json.JSONDecodeError as e:
        raise SigningFailed("Invalid key file (not valid JSON)") from e

    if not isinstance(data, dict):
        raise SigningFailed("Invalid key file: root must be a JSON object")
    if data.get("version") != 3:
        raise SigningFailed("Unsupported keystore version (expected 3)")
    if "crypto" not in data:
        raise SigningFailed("Invalid key file: missing 'crypto'")

    return data


class EncryptedFileSigner(SigningProvider):
    """
    Signing provider that imports an existing Ethereum keystore JSON file.

    The file must be created outside the SDK (e.g. Geth, MetaMask, Hardhat).
    Passphrase from constructor or env (passphrase_env); cleared from env after read when using env.
    The private key is never exposed; only signing and address are available.
    """

    def __init__(
        self,
        key_file_path: str | Path,
        passphrase: str | None = None,
        passphrase_env: str = "LEDGE_KEY_PASSPHRASE",
    ) -> None:
        path = Path(key_file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Key file not found: {path}")

        passphrase_val: str | None = passphrase
        if passphrase_val is None:
            passphrase_val = os.environ.get(passphrase_env)
            if not passphrase_val:
                raise ValueError(
                    f"Passphrase not set. Provide passphrase= or set {passphrase_env} in environment."
                )
            os.environ.pop(passphrase_env, None)

        keystore = _load_keystore(path)

        try:
            raw_key = Account.decrypt(keystore, passphrase_val)
        except Exception as e:
            raise SigningFailed("Decryption failed (wrong passphrase or corrupted file)") from e
        finally:
            del passphrase_val

        # Build account from decrypted key; wrap so .key is never exposed to agent/code
        try:
            key_hex = raw_key.hex()
            account = Account.from_key("0x" + key_hex if not key_hex.startswith("0x") else key_hex)
            self._account = _SecureAccountWrapper(account)
        except Exception as e:
            raise SigningFailed("Invalid key in file") from e
        # raw_key / key_hex go out of scope; wrapper has no .key attribute

    def sign(self, tx: dict[str, object]) -> str:
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
        try:
            if primary_type:
                domain_eip712 = _domain_to_eip712(domain)
                full_message = {
                    "types": types,
                    "primaryType": primary_type,
                    "domain": domain_eip712,
                    "message": message,
                }
                signable = encode_typed_data(full_message=full_message)
            else:
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
        return f"EncryptedFileSigner(address={self.address})"
