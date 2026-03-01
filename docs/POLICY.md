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
| `velocity_window_seconds` | 60 | Velocity check window |
| `velocity_max_tx` | 5 | Max tx in window |

See `example/policy.json` for a full config.
