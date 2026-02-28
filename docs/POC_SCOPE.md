# POC scope — what’s in, what’s stubbed, what’s out

Short overview so someone can see what works today and what’s planned.

---

## In scope (works today)

| Area | What works |
|------|------------|
| **Decision engine** | 4 layers: technical, policy, coherence, behavioral → allow / block / escalate |
| **x402 payments** | Full flow on Base Sepolia (base_testnet) and Base mainnet (base_mainnet): 402 → pay → settlement; GET and POST with JSON body |
| **Policy** | JSON config: per-tx cap, task budget, blocked addresses, allowed networks, reason length, velocity/coherence/escalation thresholds |
| **Audit** | Every attempt logged to JSONL; `get_audit_trail()` for recent events |
| **Signing** | MockSigner (tests/demos), EnvSigner (dev; key from env, wiped after load) |
| **Demos** | Loop-based mock demo (no network) and real x402 demo on Base Sepolia; both show policy in action |

---

## Stubbed / not implemented

| Area | Status |
|------|--------|
| **Transfer executor** | Stub only; raises `NotImplementedError` for on-chain transfers |
| **Production signers** | TurnkeySigner, AwsKmsSigner documented in docs/SIGNING.md as “coming”; not in repo |
| **Balance check** | Skipped when no RPC URL; no balance validation before pay |

---

## Out of scope for this POC

- Transfer / on-chain send (separate executor, next phase)
- Turnkey / AWS KMS signers (documented, not built)
- HTTP dashboard or API server
- Real-time notifications or webhooks
- LangChain / CrewAI adapters
- Agent-to-agent payment negotiation
- Chains other than Base (testnet + mainnet)

---

## How to run and try

Run all commands from the **repo root** (so `example/policy.json` and audit log paths resolve):

```bash
pip install -e ".[dev]"
pytest tests/ -v
python example/demo_mock.py
# Real x402 (needs AGENT_PRIVATE_KEY and USDC on Base Sepolia):
python example/demo_x402.py
```

See README for Quick Start and policy reference.
