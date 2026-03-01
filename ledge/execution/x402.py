"""
X402Executor — executes payments using the x402 HTTP payment protocol.

Flow:
  1. Agent wants to fetch a paid URL
  2. Executor makes HTTP GET to the URL
  3. Server returns HTTP 402 with payment requirements in headers
  4. Executor creates payment payload using x402 SDK
  5. Executor signs the payload via SigningProvider.sign_typed_data()
  6. Executor retries request with payment header
  7. Facilitator verifies + settles on Base
  8. Executor returns ExecutionResult with settlement hash

Networks:
  base_testnet → Base Sepolia (eip155:84532), facilitator: https://x402.org/facilitator
  base_mainnet → Base (eip155:8453), facilitator: https://api.cdp.coinbase.com/platform/v2/x402
"""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING, Any

import httpx

from ledge.execution.base import ExecutionResult, PaymentExecutor
from ledge.errors import ExecutionFailed
from ledge.models.transaction import Network, Transaction
from ledge.signing.base import SigningProvider

if TYPE_CHECKING:
    from x402.mechanisms.evm.types import TypedDataField

_NETWORK_IDS = {
    "base_testnet": "eip155:84532",
    "base_mainnet": "eip155:8453",
}


def _extract_tx_hash(header_value: str) -> str:
    """
    Extract on-chain tx hash from X-PAYMENT-RESPONSE.
    Some servers return a raw 0x... hash; others return base64-encoded JSON
    with a "transaction" (or similar) field.
    """
    value = header_value.strip()
    if value.startswith("0x") and len(value) == 66 and all(
        c in "0123456789abcdefABCDEF" for c in value[2:]
    ):
        return value
    try:
        decoded = base64.b64decode(value, validate=True)
        obj = json.loads(decoded.decode("utf-8"))
        if isinstance(obj, dict):
            for key in ("transaction", "tx_hash", "txHash", "tx"):
                val = obj.get(key)
                if isinstance(val, str) and val.startswith("0x"):
                    return val
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        pass
    return value


def _to_plain_dict(obj: Any) -> Any:
    """Recursively convert x402/typed-data objects to JSON-serializable dicts."""
    if isinstance(obj, dict):
        return {k: _to_plain_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_plain_dict(x) for x in obj]
    if isinstance(obj, bytes):
        return "0x" + obj.hex()
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        return {k: _to_plain_dict(v) for k, v in vars(obj).items()}
    return obj


class _X402SignerAdapter:
    """
    Adapts ledge SigningProvider to the interface expected by x402's ExactEvmScheme.
    x402 SDK calls address and sign_typed_data(domain, types, primary_type, message) -> bytes.
    """

    def __init__(self, signer: SigningProvider) -> None:
        self._signer = signer

    @property
    def address(self) -> str:
        return self._signer.address

    def sign_typed_data(
        self,
        domain: dict[str, Any],
        types: dict[str, list[TypedDataField]],
        primary_type: str,
        message: dict[str, Any],
    ) -> bytes:
        """Convert x402 format to ledge format and return signature as bytes."""
        # x402 may pass TypedDataDomain etc.; normalize to plain dicts for JSON
        domain_plain = _to_plain_dict(domain)
        message_plain = _to_plain_dict(message)
        # Convert TypedDataField list to {"name", "type"} dicts for eth_account
        types_dict: dict[str, list[dict[str, str]]] = {}
        for type_name, fields in types.items():
            types_dict[type_name] = [
                {"name": f.name, "type": f.type} for f in fields
            ]
        sig_hex = self._signer.sign_typed_data(
            domain_plain, types_dict, message_plain, primary_type=primary_type
        )
        if sig_hex.startswith("0x"):
            sig_hex = sig_hex[2:]
        return bytes.fromhex(sig_hex)


class X402Executor(PaymentExecutor):
    """
    Executes x402 payments. Uses the x402 Python SDK internally.
    Supports Base Sepolia (base_testnet) and Base mainnet (base_mainnet).
    """

    def __init__(self, network: Network = "base_testnet") -> None:
        self._network = network
        self._network_id = _NETWORK_IDS[network]

    def execute(self, tx: Transaction, signer: SigningProvider) -> ExecutionResult:
        """
        Full x402 payment flow:
        1. Create x402ClientSync with ExactEvmScheme(adapter)
        2. Create x402HTTPClientSync for 402 handling
        3. GET url; if 402, create payment payload and retry
        4. Extract settlement hash from X-PAYMENT-RESPONSE
        """
        try:
            from x402 import x402ClientSync
            from x402.http.x402_http_client import x402HTTPClientSync
            from x402.mechanisms.evm.exact import ExactEvmScheme

            adapter = _X402SignerAdapter(signer)
            scheme = ExactEvmScheme(signer=adapter)  # type: ignore[arg-type]
            client = x402ClientSync()
            client.register(self._network_id, scheme)

            http_client = x402HTTPClientSync(client)
            url = tx.endpoint_url or tx.to
            method = tx.endpoint_method
            json_body = tx.endpoint_json

            def do_request(headers: dict[str, str] | None = None) -> httpx.Response:
                req_headers = dict(headers) if headers else {}
                if method == "POST" and json_body is not None:
                    return http.post(url, json=json_body, headers=req_headers)
                return http.get(url, headers=req_headers)

            payment_was_sent = False
            with httpx.Client() as http:
                response = do_request()

                if response.status_code == 402:
                    headers_dict = dict(response.headers)
                    body = response.content

                    def get_header(name: str) -> str | None:
                        for k, v in headers_dict.items():
                            if k.lower() == name.lower():
                                return v
                        return None

                    payment_required = http_client.get_payment_required_response(
                        get_header, response.json() if body else None
                    )
                    payment_payload = client.create_payment_payload(payment_required)
                    payment_headers = http_client.encode_payment_signature_header(
                        payment_payload
                    )

                    response = do_request(headers=payment_headers)
                    payment_was_sent = True

                if response.status_code >= 400:
                    msg = (
                        f"After sending payment, server returned HTTP {response.status_code}. "
                        "Payment was not accepted — check wallet has USDC on Base Sepolia, "
                        "signature/amount match the 402 requirements, and the endpoint supports x402."
                    )
                    if response.status_code == 402:
                        msg += " (Server still returned 402 Payment Required.)"
                    try:
                        snippet = response.text[:200] if response.text else ""
                        if snippet:
                            msg += f" Response: {snippet!r}"
                    except Exception:
                        pass
                    raise ExecutionFailed(msg)

            raw_payment_response = (
                response.headers.get("X-PAYMENT-RESPONSE")
                or response.headers.get("x-payment-response")
                or response.headers.get("PAYMENT-RESPONSE")
                or response.headers.get("payment-response")
            )

            if not raw_payment_response or raw_payment_response == "0xunknown":
                if not payment_was_sent:
                    raise ExecutionFailed(
                        f"Endpoint did not require payment (no HTTP 402 from {url}). "
                        "Ensure the URL is an x402-protected resource."
                    )
                raise ExecutionFailed(
                    "No settlement hash in response (X-PAYMENT-RESPONSE missing). "
                    "Payment may not have been accepted by the server."
                )

            tx_hash = _extract_tx_hash(raw_payment_response)

            response_data: dict[str, object] | None = None
            try:
                response_data = response.json()
            except Exception:
                response_data = {"raw": response.text[:500] if response.text else ""}

            return ExecutionResult(
                tx_hash=tx_hash,
                protocol="x402",
                network=self._network,
                amount=tx.amount,
                response_data=response_data,
            )

        except ExecutionFailed:
            raise
        except Exception as e:
            raise ExecutionFailed(f"x402 payment failed: {e}") from e
