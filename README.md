# ledge-sdk

**A pluggable layer between your agent and the wallet.** Policy + 4-layer checks before any payment. Built for x402; modular for other protocols.

> Work in progress

---

## Why ledge

| Problem | Ledge |
|---------|-------|
| Agents paying without guardrails | Policy + 4-layer engine → allow / block / escalate before execution |
| Keys in `.env` | Production: KMS, Turnkey. No KMS: encrypted key file. Testing: `.env` |
| No audit trail | Every attempt logged (JSONL) with task_id, amount, context, decision |
| Per-call approval | Operator sets policy; agent pays within limits |

---

## Quick Start

```python
from ledge import Wallet, EnvSigner, load_policy, X402Params

wallet = Wallet(
    policy=load_policy("policy.json"),
    signer=EnvSigner(),
    network="base_testnet",
)
```

**Direct payment** — one-off, no task context:

```python
result = wallet.pay(
    amount=0.01,
    to="0xPayTo...",
    context="Fetch price feed",
    params=X402Params(url="https://api.example.com/prices"),
)
```

**Batch** — multiple payments, shared budget:

```python
with wallet.task("Research DeFi", budget=0.50) as task:
    for url, amt in [("https://api.example.com/defi", 0.01), ("...", 0.005)]:
        result = task.pay(amt, "0xPayTo...", "Fetch data", params=X402Params(url=url))
        print(f"✅ {result.tx_hash}  ${list(wallet.balances().values())[0]:.2f} left")
```

---

## How it works

1. **Agent** calls `wallet.pay(...)` or `task.pay(...)`
2. **Ledge** runs 4 layers: technical → policy → coherence → behavioral. Coherence (Layer 3) uses word overlap (v1); set `coherence_weight: 0` in policy to disable it. An embedding-based version is planned.
3. **Outcome**: ALLOW (execute) / BLOCK (reject) / ESCALATE (log, notify)
4. Only on ALLOW does the wallet sign and execute

Policy is JSON. See [docs/POLICY.md](docs/POLICY.md).

---

## Outcomes

| Outcome | Meaning |
|---------|---------|
| **ALLOW** | `PayResult` with `tx_hash`, `amount`, `risk_score` |
| **BLOCK** | `TransactionBlocked` — policy violated |
| **ESCALATE** | `TransactionEscalated` — risk over threshold |
| — | `ExecutionFailed` — payment execution failed |

All logged to audit trail.

---

## Key handling

| Use | Provider |
|-----|----------|
| Production | Turnkey, AWS KMS (coming) |
| No .env, no KMS | Encrypted key file (planned) |
| Quick test | EnvSigner (`.env`) |
| Tests | MockSigner |

[docs/SIGNING.md](docs/SIGNING.md)

---

## Run

```bash
pip install -e .
pytest tests/ -v
python example/demo_mock.py    # mock, no network
python example/demo_x402.py    # real x402 (needs AGENT_PRIVATE_KEY + USDC)
```

---

## Extend

| What | How |
|------|-----|
| Policy | JSON → [docs/POLICY.md](docs/POLICY.md) |
| Signing | `SigningProvider` → [docs/SIGNING.md](docs/SIGNING.md) |
| Protocol | `PaymentExecutor` → [docs/EXECUTORS.md](docs/EXECUTORS.md) |
