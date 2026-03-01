<h2 align="center">Work in Progress !!</h2>

# ledge-sdk 

**Let your agent pay for x402 APIs within a per-task budget — with policy and audit, no per-call approval.**

Before any payment executes, ledge runs it through a 4-layer decision engine (technical → policy → coherence → behavioral), then **allows**, **blocks**, or **escalates**. Built for x402; modular for other protocols.

## Install

Clone the repo, then from the repo root:

```bash
pip install -e .
```

Requires Python 3.10+. Get test USDC for Base Sepolia at https://faucet.circle.com

## Quick Start

```python
from ledge import Wallet, EnvSigner, load_policy
from ledge import TransactionBlocked, TransactionEscalated, ExecutionFailed

wallet = Wallet(
    policy=load_policy("policy.json"),
    signer=EnvSigner(),          # reads AGENT_PRIVATE_KEY from .env (wiped after load — one Wallet per process)
    network="base_testnet",      # Base Sepolia — use "base_mainnet" for production
)
```

### Simple: Direct single payment

**Use when:** One-off payment, no need to group multiple calls under a shared budget. Each call gets a unique task_id for tracing.

```python
result = wallet.pay(
    description="Fetch market data",
    budget=0.01,
    amount_usd=0.01,
    to="0xPayToAddress...",
    reason="One-time API call for price feed",
    endpoint_url="https://api.example.com/prices",
)
print(f"Settled: {result.tx_hash}")
```

### Batch: Task-scoped multi-payment

**Use when:** Multiple related payments that share one budget (e.g. fetching from several APIs in a single task). All payments in the block share the same task_id and budget.

```python
with wallet.task("Research DeFi protocols", budget=0.50) as task:
    for url, amount in [
        ("https://api.example.com/defi", 0.01),
        ("https://api.example.com/prices", 0.005),
    ]:
        try:
            result = task.pay(
                amount_usd=amount,
                to="0xPayToAddress...",
                reason="Fetch DeFi market data from paid API",
                endpoint_url=url,
            )
            print(f"Settled: {result.tx_hash}  remaining: ${list(wallet.balances().values())[0]:.2f}")
        except TransactionBlocked as e:
            print(f"Blocked: {e.check_name} — {e.reason}")
            break
        except TransactionEscalated as e:
            print(f"Escalated (risk={e.risk_score:.2f}) — log or notify operator")
            break
        except ExecutionFailed as e:
            print(f"Execution failed: {e}")
            break
```

**Audit:** Direct payments use task_id prefix `direct-`; batch tasks get a UUID. Filter with `task_id.startswith(DIRECT_PAY_TASK_PREFIX)` for ad-hoc payments.

## How It Works

**Layer 1 — Technical.** Can this transaction physically execute? The engine validates the destination address format, checks that sufficient balance exists (when RPC is configured), and optionally dry-runs the transaction via `eth_call` before signing. For x402, simulation is skipped because it is an HTTP call, not an on-chain transaction.

**Layer 2 — Policy.** Operator-defined hard rules. Any failure means BLOCK. The engine enforces per-transaction amount caps, task budget limits, blocked address lists, allowed networks, and minimum reason length. These are configured in a JSON policy file.

**Layer 3 — Coherence.** Does this payment make sense for the current task? The engine compares the payment reason to the task description using word overlap. Low overlap increases risk. Empty task descriptions get the benefit of the doubt.

**Layer 4 — Behavioral.** Is the agent behaving normally? The engine scores transaction velocity (too many in a time window), amount anomalies (outliers vs historical average), and repeat destinations (possible loops). These contribute to a weighted risk score.

If any hard check (layers 1–2) fails, the outcome is BLOCK. If all pass, soft checks (layers 3–4) contribute to a risk score. If risk exceeds the policy threshold, the outcome is ESCALATE. Otherwise, ALLOW — and the executor signs and submits the payment.

## Networks

| network= | Chain | Facilitator |
|----------|-------|-------------|
| "base_testnet" | Base Sepolia (eip155:84532) | https://x402.org/facilitator |
| "base_mainnet" | Base mainnet (eip155:8453) | https://api.cdp.coinbase.com/platform/v2/x402 |

## Decision Outcomes

Three possible outcomes from every `task.pay()` call:

- **ALLOW** → `PayResult` returned with `tx_hash`, `amount_usd`, `risk_score`, etc.
- **BLOCK** → `TransactionBlocked` raised with `reason` and `check_name`
- **ESCALATE** → `TransactionEscalated` raised with `reason` and `risk_score`

All three are logged to the audit trail.

**Handling outcomes:** Catch `TransactionBlocked` (policy violated — stop or adjust), `TransactionEscalated` (risk over threshold — log, notify operator, or retry with smaller amount), and `ExecutionFailed` (payment execution failed — check wallet/network and retry or alert).

## Policy Configuration

| Field | Default | Description |
|-------|---------|--------------|
| `simulate_before_sign` | `false` | Dry-run on-chain tx before signing (x402 skips) |
| `max_amount_usd_per_tx` | `10.0` | Per-transaction cap in USD |
| `max_spend_usd_per_task` | `50.0` | Total spend cap per task |
| `allowed_networks` | `["base_testnet","base_mainnet"]` | Networks the agent may use |
| `blocked_addresses` | `[]` | Deny-list of destination addresses |
| `require_reason` | `true` | Require a non-empty payment reason |
| `min_reason_length` | `10` | Minimum characters in reason |
| `coherence_weight` | `0.4` | Weight for coherence risk |
| `velocity_window_seconds` | `60` | Time window for velocity check |
| `velocity_max_tx` | `5` | Max transactions in window |
| `velocity_weight` | `0.35` | Weight for velocity risk |
| `anomaly_multiplier_threshold` | `3.0` | Amount vs avg to flag anomaly |
| `anomaly_weight` | `0.25` | Weight for anomaly risk |
| `escalate_risk_threshold` | `0.65` | Risk score above which to ESCALATE |

## Audit Trail

Every payment attempt is logged, regardless of outcome:

```python
for event in wallet.get_audit_trail(10):
    print(f"{event.outcome}: ${event.amount_usd:.4f} — {event.decision_reason}")
```

Events are appended to a JSONL file (one JSON object per line). View a single event:

```bash
head -1 ledge_audit.jsonl | python -m json.tool
```

## Signing Providers

| Provider | Use | Key location |
|----------|-----|--------------|
| MockSigner | Tests and demos | No real key |
| EnvSigner | Local development | .env — key read once then wiped (one Wallet per process, or set env before each EnvSigner) |
| TurnkeySigner | Production (coming) | Turnkey TEE |
| AwsKmsSigner | Teams on AWS (coming) | AWS KMS |

See [docs/SIGNING.md](docs/SIGNING.md) for the full guide.

## Running the Tests

From the repo root:

```bash
# Install in editable mode with dev dependencies (pytest, mypy, ruff, pre-commit, etc.)
pip install -e ".[dev]"

# Run all tests (excluding the manual x402 integration test)
pytest tests/ -v --ignore=tests/test_execution_x402.py
```

**Pre-commit (lint before every commit):**

```bash
pip install -e ".[dev]"
pre-commit install
```

After that, every `git commit` runs ruff (with auto-fix), mypy, and basic checks (trailing whitespace, end-of-file, etc.). To run the same checks manually: `pre-commit run --all-files`.

To run a specific test file or test:

```bash
pytest tests/test_wallet.py -v
pytest tests/test_wallet.py::test_happy_path -v
```

## Running the Demos

From repo root (after `pip install -e .`):

```bash
# No wallet needed — shows ALLOW, BLOCK, ESCALATE
python example/demo_mock.py

# Real x402 on Base Sepolia (requires AGENT_PRIVATE_KEY and USDC)
python example/demo_x402.py
```

For a short “what’s in this POC” overview, see [docs/POC_SCOPE.md](docs/POC_SCOPE.md).

## Modularity

The SDK is built so you can plug in your own pieces without forking:

| Extension point | What you provide | Doc |
|-----------------|------------------|-----|
| **Policy** | JSON (or build `Policy` in code) | This README, Policy Configuration |
| **Signing** | `SigningProvider` (e.g. KMS, Turnkey) | [docs/SIGNING.md](docs/SIGNING.md) |
| **Execution** | `PaymentExecutor` per protocol | [docs/EXECUTORS.md](docs/EXECUTORS.md) |

New protocol: implement `PaymentExecutor`, then `wallet._executors["my_protocol"] = MyExecutor()`. Engine and policy stay unchanged.

## Adding a New Payment Protocol

1. Create `ledge/execution/my_protocol.py`
2. Subclass `PaymentExecutor`
3. Implement `execute(tx, signer) -> ExecutionResult`
4. Register: `wallet._executors["my_protocol"] = MyExecutor()` (or replace existing, e.g. for tests).

See [docs/EXECUTORS.md](docs/EXECUTORS.md) for the full guide.
