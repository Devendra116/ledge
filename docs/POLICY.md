# Policy

Policy is a JSON file. Load with `load_policy("policy.json")`.

## Minimal example

```json
{
  "max_amount_usd_per_tx": 1,
  "max_spend_usd_per_task": 5,
  "allowed_networks": ["base_testnet", "base_mainnet"],
  "escalate_risk_threshold": 0.65
}
```

## Fields

| Field | Default | Description |
|-------|---------|-------------|
| `max_amount_usd_per_tx` | 10 | Per-transaction cap |
| `max_spend_usd_per_task` | 50 | Task budget cap |
| `allowed_networks` | base_testnet, base_mainnet | Allowed chains |
| `blocked_addresses` | [] | Deny-list |
| `require_reason` | true | Require non-empty context |
| `min_reason_length` | 10 | Min chars in context |
| `escalate_risk_threshold` | 0.65 | Risk above → ESCALATE |
| `simulate_before_sign` | false | Layer 1: dry-run on-chain tx (x402 skips) |
| `velocity_window_seconds` | 60 | Layer 4: velocity window (seconds) |
| `velocity_max_tx` | 5 | Layer 4: max tx in window |
| `velocity_weight` | 0.35 | Layer 4: velocity risk weight |
| `anomaly_multiplier_threshold` | 3.0 | Layer 4: amount vs avg to flag outlier |
| `anomaly_weight` | 0.25 | Layer 4: anomaly risk weight |
| `coherence_weight` | 0.4 | Layer 3: coherence risk weight; set to `0` to disable |

## Layers

The engine runs four layers in order. Layers 1–2 are **hard** (any failure → BLOCK). Layers 3–4 are **soft** (they contribute to a risk score; if total risk ≥ `escalate_risk_threshold` → ESCALATE).

### Layer 1 — Technical

Can this transaction physically execute? Checks: **address format** (valid Ethereum address), **balance** (skipped if no `WEB3_RPC_URL`), **simulation** (dry-run via `eth_call`; skipped for x402 and when `simulate_before_sign` is false). No policy fields required for address/network basics; use `simulate_before_sign` to enable pre-sign simulation for on-chain transfers.

### Layer 2 — Policy

Operator-defined hard rules. Any failure → BLOCK. Checks: **amount limit** (`max_amount_usd_per_tx`), **budget** (remaining task budget), **blocked_addresses**, **allowed_networks**, **reason** (context required and `min_reason_length` when `require_reason` is true).

### Layer 3 — Coherence

Does the payment context match the task description? Current implementation uses **word overlap** (v1). Contributes to risk; set `coherence_weight` to `0` to disable. A semantic (embedding-based) version is planned for production.

### Layer 4 — Behavioral

Is the agent behaving normally? Soft checks that add risk: **velocity** (too many tx in `velocity_window_seconds`; limit `velocity_max_tx`), **amount_anomaly** (tx amount far above task average), **repeat_destination** (same address hit 3+ times in window — possible loop). Tuned by `velocity_weight`, `anomaly_weight`, and thresholds.

---

See `example/policy.json` for a full config.
