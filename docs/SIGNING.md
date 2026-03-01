# Signing Providers

The signing interface has two methods:
- `sign(tx: dict) -> str` — for on-chain transactions (TransferExecutor)
- `sign_typed_data(domain, types, message) -> str` — for EIP-712 (X402Executor)

Ledge avoids requiring keys in `.env` for production. Use a production signer or encrypted key file; reserve `.env` for quick local testing.

## Available Now

| Provider   | Use                  | Key location                         |
|-----------|----------------------|--------------------------------------|
| MockSigner| Tests and demos      | No real key                          |
| EnvSigner | Quick local testing  | .env file — wiped from env on load   |

## Coming Soon

| Provider      | Use                    | Key location                              |
|--------------|------------------------|-------------------------------------------|
| TurnkeySigner| Production              | Turnkey TEE — key never leaves hardware   |
| AwsKmsSigner | Production (AWS teams) | AWS KMS                                   |
| Encrypted key file | No .env, no KMS   | Encrypted key in file; unlock with passphrase/env |
| VaultSigner  | Enterprise              | HashiCorp Vault transit engine            |

## Adding Your Own

```python
from ledge.signing.base import SigningProvider

class MyCustomSigner(SigningProvider):
    def sign(self, tx: dict) -> str: ...
    def sign_typed_data(self, domain, types, message) -> str: ...

    @property
    def address(self) -> str: ...
```
