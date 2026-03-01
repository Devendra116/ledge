# Signing Providers

Two methods: `sign(tx)` for on-chain tx, `sign_typed_data(domain, types, message)` for EIP-712 (x402).

## Key isolation (agent / untrusted code)

**Do not give the agent or untrusted code a reference to the signer.** Expose only the `Wallet` (and `task.pay` / `wallet.pay`). If the agent could do `wallet._signer._account.key`, it could steal the key — so we make that impossible:

- **No `.key` on the signer’s account:** The internal account is wrapped. Access to `.key`, `.private_key`, or the inner account from outside the SDK raises `AttributeError`. Only `sign()`, `sign_typed_data()`, and `address` are available.
- **No pickling:** `SigningProvider` instances cannot be pickled, so they cannot be serialized (e.g. to send to another process or to log).
- **No key in errors or repr:** Exception messages and `repr(signer)` never contain key material or passphrase.
- **Passphrase / key in `.env`:** For **local testing only**, you may put the key or passphrase in `.env`. The key is still wiped from the environment after load and is not exposed via the signer object. For production, use a keystore file (EncryptedFileSigner) or KMS; never rely on the agent having access to `.env` or the signer.

- **Best security:** For highest assurance, use an out-of-process signer or KMS (e.g. Turnkey, AWS KMS when available) so the key never lives in the agent process.

## Available Now

| Provider            | Use                     | Key location                              |
|---------------------|-------------------------|-------------------------------------------|
| MockSigner          | Tests and demos         | No real key                               |
| EnvSigner           | Quick local testing     | .env — wiped from env on load             |
| EncryptedFileSigner | No .env, no KMS         | Ethereum keystore JSON; passphrase from env or arg |

### EncryptedFileSigner

**Import only.** The SDK does not create key files. You use an existing **Ethereum keystore JSON file** (version 3), e.g. from Geth, MetaMask, Hardhat, or any tool that exports that format. Passphrase from env or constructor; never logged. Env var is cleared after read when using `passphrase_env`. The private key is never exposed to the agent or to code — no getter, no repr, no logging.

**Use in Wallet:**

```python
from ledge import EncryptedFileSigner, Wallet, load_policy

signer = EncryptedFileSigner(
    "path/to/keystore.json",   # existing keystore file (create it outside the SDK)
    passphrase_env="LEDGE_KEY_PASSPHRASE",  # or passphrase="..."
)
wallet = Wallet(policy=load_policy("policy.json"), signer=signer, network="base_testnet")
```

To create a keystore file outside the SDK, use Geth/MetaMask/Hardhat or a small script with `eth_account.Account.encrypt(account.key, password)` and save the dict as JSON.

## Coming Soon

| Provider      | Use                    | Key location                    |
|---------------|------------------------|---------------------------------|
| TurnkeySigner | Production             | Turnkey TEE                     |
| AwsKmsSigner  | Production (AWS)        | AWS KMS                         |
| VaultSigner   | Enterprise              | HashiCorp Vault                 |

## Adding Your Own

```python
from ledge.signing.base import SigningProvider

class MyCustomSigner(SigningProvider):
    def sign(self, tx: dict) -> str: ...
    def sign_typed_data(self, domain, types, message) -> str: ...

    @property
    def address(self) -> str: ...
```
