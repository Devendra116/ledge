# Ledge

**A policy layer between your AI agent and the wallet.**

AI agents are starting to make payments autonomously — calling paid APIs, buying data, paying for compute. But right now, there's nothing between the agent and your money. No spending limits. No audit trail. No way to say "block this" or "escalate that."

Ledge sits in between. Before any payment executes, it runs a 4-layer check (technical, policy, coherence, behavioral) and decides: **allow**, **block**, or **escalate**.

> Early stage — actively building. If this is close to a problem you're facing, or you'd build it differently, I'd love to hear from you (see [Reach out](#reach-out) below).

---

## See it in action

### 1. Setup — define policy and create a wallet

```python
from ledge import Wallet, EnvSigner, load_policy, X402Params

wallet = Wallet(
    policy=load_policy("policy.json"),   # your rules (JSON)
    signer=EnvSigner(),                  # key handling
    network="base_testnet",
)
```

Your policy is a simple JSON file — set per-transaction caps, task budgets, blocked addresses, and risk thresholds:

```json
{
  "max_amount_usd_per_tx": 1.0,
  "max_spend_usd_per_task": 5.0,
  "allowed_networks": ["base_testnet", "base_mainnet"],
  "escalate_risk_threshold": 0.65
}
```

### 2. Single payment — agent pays for one API call

```python
result = wallet.pay(
    amount=0.01,
    to="0xPayTo...",
    context="Fetch price feed from CoinGecko",
    params=X402Params(url="https://api.example.com/prices"),
)
# → ALLOW: tx=0x3fa9..., risk_score=0.08
```

The agent asked to spend $0.01. Ledge checked:
- Is the address valid? (Layer 1 — technical)
- Is $0.01 under the $1.00 per-tx limit? (Layer 2 — policy)
- Does "Fetch price feed" make sense in context? (Layer 3 — coherence)
- Is the agent behaving normally — no rapid-fire payments or anomalies? (Layer 4 — behavioral)

All clear. Payment goes through.

### 3. What a block looks like

```python
wallet.pay(amount=1.50, to="0xPayTo...", context="Large purchase", params=X402Params(url="..."))
# → BLOCK: amount $1.50 exceeds per-tx limit $1.00
```

$1.50 exceeds the $1.00 per-tx cap in your policy. Ledge blocks it instantly. No funds leave.

### 4. Task with a shared budget — the real use case

Your agent has a job to do ("Research DeFi protocols") and needs to call multiple paid APIs. You give it a budget. Ledge tracks spending across all payments in the task.

```python
with wallet.task("Research DeFi protocols", budget=0.02) as task:

    task.pay(0.01, "0xPayTo...", "Fetch DeFi protocol data", params=X402Params(url="https://api.example.com/defi"))
    # → ALLOW — spent $0.01, budget remaining: $0.01

    task.pay(0.01, "0xPayTo...", "Fetch lending rates", params=X402Params(url="https://api.example.com/rates"))
    # → ALLOW — spent $0.02, budget remaining: $0.00

    task.pay(0.01, "0xPayTo...", "Fetch TVL data", params=X402Params(url="https://api.example.com/tvl"))
    # → BLOCK — budget exceeded ($0.02 / $0.02 used)
```

The third payment is blocked — not because anything is wrong with it, but because the task budget is exhausted. The agent can't overspend.

### 5. Escalation — something looks off

If payments come too fast, amounts spike, or the context doesn't match the task, the risk score climbs. Cross the threshold and Ledge escalates instead of executing.

```python
with wallet.task("Research DeFi protocols", budget=0.10) as task:
    for i in range(6):
        task.pay(0.005, "0xPayTo...", "Fetch DeFi data", params=X402Params(url="https://api.example.com/data"))

# First few → ALLOW (risk: 0.12, 0.25, 0.38, ...)
# Eventually → ESCALATE (risk: 0.68 — above 0.65 threshold)
```

Five rapid payments to the same address triggered the velocity and repeat-destination checks. Risk crossed 0.65. Ledge escalates — the payment is logged but not executed.

### 6. Audit trail — every decision is logged

```python
for event in wallet.get_audit_trail(5):
    print(f"{event.outcome}  ${event.amount:.4f}  {event.decision_reason}")

# allow      $0.0100  all checks passed; risk 0.08
# allow      $0.0100  all checks passed; risk 0.15
# block      $0.0100  budget exceeded
# allow      $0.0050  all checks passed; risk 0.25
# escalate   $0.0050  risk 0.68 >= threshold 0.65
```

Every attempt — allowed, blocked, or escalated — is logged to a JSONL file with the task ID, amount, context, and full decision breakdown.

---

## How the 4 layers work

Every payment goes through these layers in order:

| Layer | What it checks | Hard/Soft |
|-------|---------------|-----------|
| **1. Technical** | Valid address? Sufficient balance? Simulate tx? | Hard — any failure blocks |
| **2. Policy** | Under per-tx cap? Within budget? Network allowed? Reason provided? Address not blocked? | Hard — any failure blocks |
| **3. Coherence** | Does the payment context match the task description? | Soft — adds to risk score |
| **4. Behavioral** | Too many tx too fast? Amount spike? Same destination on repeat? | Soft — adds to risk score |

Layers 1–2 are binary: pass or block. Layers 3–4 contribute to a risk score. If the combined score crosses your `escalate_risk_threshold`, the payment is escalated (logged, not executed).

---

## Key handling

| Scenario | What to use |
|----------|------------|
| Local testing | `EnvSigner` — key from `.env` |
| No KMS, no `.env` | `EncryptedFileSigner` — Ethereum keystore JSON + passphrase |
| Production | Turnkey, AWS KMS (planned) |
| Tests/demos | `MockSigner` |

The agent only sees the `Wallet` object (`wallet.pay`, `task.pay`). It never gets access to the signer or the raw key. See [docs/SIGNING.md](docs/SIGNING.md).

---

## Try it

```bash
pip install -e .
pytest tests/ -v

# Mock demo (no network, no keys needed)
python example/demo_mock.py

# Real x402 payment on Base Sepolia (needs AGENT_PRIVATE_KEY + USDC)
python example/demo_x402.py
```

---

## Current status

This is an early-stage project. Here's what works today and what's coming:

**Working:**
- 4-layer decision engine (technical, policy, coherence, behavioral)
- x402 payments on Base Sepolia and Base mainnet
- Policy config via JSON
- Audit logging (JSONL)
- MockSigner, EnvSigner, EncryptedFileSigner

**Coming next:**
- On-chain transfer executor (direct USDC sends)
- Turnkey / AWS KMS signers for production key management
- Semantic coherence check (embedding-based, replacing word overlap)
- More chains beyond Base

**Not planned for this phase:**
- HTTP dashboard or API server
- LangChain / CrewAI adapters
- Agent-to-agent payment negotiation

Full scope breakdown: [docs/POC_SCOPE.md](docs/POC_SCOPE.md)

---

## Extend

| What | How |
|------|-----|
| Policy rules | JSON config → [docs/POLICY.md](docs/POLICY.md) |
| Signing providers | Implement `SigningProvider` → [docs/SIGNING.md](docs/SIGNING.md) |
| Payment protocols | Implement `PaymentExecutor` → [docs/EXECUTORS.md](docs/EXECUTORS.md) |

---

## Reach out

I'm building this to solve a real problem — agents spending money need guardrails. If you're dealing with something similar, or if you'd approach it differently, I want to hear from you.

- Have a use case that's close but not quite covered? Let me know.
- Want a feature? Open an issue or message me directly.
- Think the approach is wrong? I'd rather hear it now.

**Twitter:** [@devendra_116](https://x.com/devendra_116) | **Telegram:** [@devendra116](https://t.me/devendra116)
