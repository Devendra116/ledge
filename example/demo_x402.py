"""
Ledge SDK — Real x402 Demo on Base Sepolia

Loop-based: simulates an agent calling multiple x402-paid endpoints in sequence.
Policy (budget, amount limit) is tested as we iterate; remaining budget shown after each pay.

Requirements:
  1. Copy example/.env.example to example/.env (or project root .env)
  2. Set AGENT_PRIVATE_KEY to a wallet with USDC on Base Sepolia
  3. Get test USDC: https://faucet.circle.com (select Base Sepolia)
  4. Get test ETH:  https://www.alchemy.com/faucets/base-sepolia

Run from repo root (after: pip install -e .):
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
)
from ledge.models import X402Params

load_dotenv()

# Endpoints to try in sequence (real payments). Budget is consumed; policy can block.
X402_TEST_ENDPOINTS = [
    {
        "url": "https://api.simplescraper.io/v1/extract",
        "payto": "0x0000000000000000000000000000000000000000",
        "description": "SimpleScraper extract (POST)",
        "expected_amount": 0.001,
        "method": "POST",
        "json": {"url": "https://example.com", "markdown": True},
    },
    {
        "url": "https://www.x402.org/protected",
        "payto": "0x0000000000000000000000000000000000000000",
        "description": "x402.org protected endpoint",
        "expected_amount": 0.01,
        "method": "GET",
        "json": None,
    },
    {
        "url": "https://www.x402.org/protected",
        "payto": "0x0000000000000000000000000000000000000000",
        "description": "x402.org protected endpoint",
        "expected_amount": 1,
        "method": "GET",
        "json": None,
    },
    {
        "url": "https://www.x402.org/protected",
        "payto": "0x0000000000000000000000000000000000000000",
        "description": "x402.org protected endpoint",
        "expected_amount": 0.01,
        "method": "GET",
        "json": None,
    }
]


def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print("─" * 60)


def main() -> None:
    print("\n🏦 Ledge SDK — Real x402 Demo (loop)")
    print("   Network: Base Sepolia (base_testnet)")
    print("   Protocol: x402 | Token: USDC")

    if not os.environ.get("AGENT_PRIVATE_KEY"):
        print("\n❌ AGENT_PRIVATE_KEY not set in .env")
        print("   Copy .env.example to .env and set your key")
        print("   Get test USDC: https://faucet.circle.com (Base Sepolia)")
        sys.exit(1)

    policy = load_policy("example/policy.json")
    signer = EnvSigner(env_var="AGENT_PRIVATE_KEY")
    print(f"\n   Wallet: {signer.address}")

    wallet = Wallet(
        policy=policy,
        signer=signer,
        network="base_testnet",
        audit_logger=AuditLogger("./demo_x402_audit.jsonl"),
        agent_id="research-agent-01",
    )

    task_description = "Fetch data from x402-protected APIs (loop)"
    budget = 0.05  # Small budget so we can see policy block when exhausted

    section(f"Task: {task_description} (budget ${budget:.4f})")
    print("  Looping over endpoints until budget used or policy blocks.\n")

    with wallet.task(description=task_description, budget=budget) as task:
        for i, ep in enumerate(X402_TEST_ENDPOINTS):
            amount = ep["expected_amount"]
            print(f"  #{i+1}  {ep['description'][:45]}  (${amount:.4f})  ", end="")
            try:
                result = task.pay(
                    amount=amount,
                    to=ep["payto"],
                    context=f"Fetch data from {ep['description']}",
                    protocol="x402",
                    params=X402Params(
                        url=ep["url"],
                        method=ep.get("method", "GET"),
                        body=ep.get("json"),
                    ),
                )
                remaining = next(iter(wallet.balances().values()), 0)
                print(f"✅ ALLOW   remaining ${remaining:.4f}  tx={result.tx_hash}")
            except TransactionBlocked as e:
                print(f"🚫 BLOCK  {e.check_name}: {e.reason[:40]}")
            except TransactionEscalated as e:
                print(f"⚠️  ESCALATE  risk={e.risk_score:.2f}  {e.reason[:40]}")
            except ExecutionFailed as e:
                print(f"❌ EXECUTION FAILED: {e}")

    section("Audit Trail")
    for event in wallet.get_audit_trail(8):
        icon = {"allow": "✅", "block": "🚫", "escalate": "⚠️ "}.get(event.outcome, "?")
        print(
            f"  {icon} {event.outcome.upper():8s} | "
            f"${event.amount:.4f} | "
            f"{event.decision_reason[:50]}"
        )

    print("\n📋 Full audit: ./demo_x402_audit.jsonl\n")


if __name__ == "__main__":
    main()
