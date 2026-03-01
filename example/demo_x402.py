"""
Ledge SDK — Real x402 demo (Base Sepolia): direct pay, group task, BLOCK/ESCALATE.

  Needs: AGENT_PRIVATE_KEY in .env, USDC on Base Sepolia (faucet.circle.com)
  python example/demo_x402.py
"""
import os
import sys

from dotenv import load_dotenv

from ledge import (
    AuditLogger,
    EnvSigner,
    ExecutionFailed,
    TransactionBlocked,
    TransactionEscalated,
    Wallet,
    load_policy,
    X402Params,
)

load_dotenv()

# Real x402 endpoints (Base Sepolia)
ENDPOINTS = [
    {"url": "https://www.x402.org/protected", "payto": "0x0000000000000000000000000000000000000000", "amount": 0.01},
    {"url": "https://www.x402.org/protected", "payto": "0x0000000000000000000000000000000000000000", "amount": 0.01},
    {"url": "https://api.simplescraper.io/v1/extract", "payto": "0x0000000000000000000000000000000000000000", "amount": 0.001, "method": "POST", "body": {"url": "https://example.com", "markdown": True}},
]


def run(wallet: Wallet) -> None:
    # --- 1. Direct payment (real) ---
    print("1. Direct payment")
    ep = ENDPOINTS[0]
    print(f"   pay(0.01, {ep['url'][:35]}...) ", end="")
    try:
        r = wallet.pay(
            amount=ep["amount"],
            to=ep["payto"],
            context="Fetch from x402 protected endpoint",
            params=X402Params(url=ep["url"]),
        )
        print(f"→ ALLOW  tx={r.tx_hash}...")
    except TransactionBlocked as e:
        print(f"→ BLOCK  [{e.check_name}]")
    except TransactionEscalated as e:
        print(f"→ ESCALATE  risk={e.risk_score:.2f}")
    except ExecutionFailed as e:
        print(f"→ FAIL  {e}")

    # --- 2. Direct: intentional BLOCK (over limit) ---
    print("   pay(1.50, ...) ", end="")
    try:
        wallet.pay(amount=1.50, to=ep["payto"], context="Over per-tx limit", params=X402Params(url=ep["url"]))
    except TransactionBlocked as e:
        print(f"→ BLOCK  [{e.check_name}] {e.reason[:40]}")

    # --- 3. Group task (real pays until budget or policy) ---
    print("\n2. Group task (budget 0.02)")
    with wallet.task("Fetch x402 APIs", budget=0.02) as task:
        for i, ep in enumerate(ENDPOINTS, 1):
            try:
                params = X402Params(url=ep["url"], method=ep.get("method", "GET"), body=ep.get("body"))
                r = task.pay(ep["amount"], ep["payto"], f"Fetch from {ep['url'][:30]}", params=params)
                left = next(iter(wallet.balances().values()), 0)
                print(f"   #{i} ${ep['amount']:.3f} → ALLOW  remaining ${left:.2f}  tx={r.tx_hash}...")
            except TransactionBlocked as e:
                print(f"   #{i} ${ep['amount']:.3f} → BLOCK  [{e.check_name}]")
                break
            except TransactionEscalated as e:
                print(f"   #{i} → ESCALATE  risk={e.risk_score:.2f}")
                break
            except ExecutionFailed as ex:
                print(f"   #{i} → FAIL  {ex}")
                break

    # --- 4. Audit ---
    print("\n3. Audit (last 6)")
    for ev in wallet.get_audit_trail(6):
        icon = {"allow": "✅", "block": "🚫", "escalate": "⚠️"}[ev.outcome]
        print(f"   {icon} {ev.outcome:8} ${ev.amount:.4f}  {ev.decision_reason[:42]}")


def main() -> None:
    if not os.environ.get("AGENT_PRIVATE_KEY"):
        print("AGENT_PRIVATE_KEY not set. Use .env and get USDC from faucet.circle.com (Base Sepolia)")
        sys.exit(1)

    print("Ledge x402 demo — direct pay, group task (Base Sepolia)\n")
    policy = load_policy("example/policy.json")
    signer = EnvSigner(env_var="AGENT_PRIVATE_KEY")
    wallet = Wallet(
        policy=policy,
        signer=signer,
        network="base_testnet",
        audit_logger=AuditLogger("./demo_x402_audit.jsonl"),
    )
    print(f"Wallet: {signer.address}\n")
    run(wallet)
    print("\nAudit: ./demo_x402_audit.jsonl")


if __name__ == "__main__":
    main()
