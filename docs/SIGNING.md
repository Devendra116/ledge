# Signing Providers

The signing interface has two methods:
- `sign(tx: dict) -> str` — for on-chain transactions (TransferExecutor)
- `sign_typed_data(domain, types, message) -> str` — for EIP-712 (X402Executor)

## Available Now

| Provider   | Use             | Key location                    |
|-----------|-----------------|----------------------------------|
| MockSigner| Tests and demos | No real key                     |
| EnvSigner | Local development | .env file — wiped from env on load |

## Coming Soon

| Provider      | Use             | Key location                     |
|--------------|-----------------|-----------------------------------|
| TurnkeySigner| Production web3 | Turnkey TEE — key never leaves hardware |
| AwsKmsSigner | Teams on AWS    | AWS KMS — ~$0.03 per 10k requests |
| VaultSigner  | Enterprise      | HashiCorp Vault transit engine   |

## Adding Your Own

```python
from ledge.signing.base import SigningProvider

class MyCustomSigner(SigningProvider):
    def sign(self, tx: dict) -> str: ...
    def sign_typed_data(self, domain, types, message) -> str: ...

    @property
    def address(self) -> str: ...
```
