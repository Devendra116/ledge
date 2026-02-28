"""
Ledge SDK — Mock Demo

Loop-based demo: simulates an agent making multiple paid API calls in sequence.
Exercises policy (budget, velocity, coherence) and shows ALLOW / BLOCK / ESCALATE.

Run from repo root (after: pip install -e .):
  python example/demo_mock.py
"""
from dotenv import load_dotenv

from ledge import (
    AuditLogger,
    TransactionBlocked,
    TransactionEscalated,
    Wallet,
    load_policy,
)
from ledge.execution.base import ExecutionResult, PaymentExecutor
from ledge.models.transaction import Transaction
from ledge.signing.base import SigningProvider
from ledge.signing.mock_signer import MockSigner

load_dotenv()


class _MockX402Executor(PaymentExecutor):
    """Fake executor for demo — returns a mock hash without network calls."""

    def execute(self, tx: Transaction, signer: SigningProvider) -> ExecutionResult:
        return ExecutionResult(
            tx_hash=f"0xMOCK_SETTLEMENT_{tx.amount_usd:.4f}",
            protocol="x402",
            network=tx.network,
            amount_usd=tx.amount_usd,
            response_data={"data": "mock API response", "price": tx.amount_usd},
        )


def section(title: str) -> None:
    print(f"\n{'─' * 55}")
    print(f"  {title}")
    print("─" * 55)


# Real-world style: list of tasks, each with a budget and a list of payment attempts.
# Policy is tested as we loop: budget decreases, velocity builds, block/escalate when triggered.
SCENARIOS = [
    {
        "name": "Research DeFi protocols by TVL",
        "budget": 0.05,
        "pays": [
            {"amount": 0.01, "to": "0x742d35Cc6634C0532925a3b8D4C9C3E0a1b2f3A4", "reason": "Fetch DeFi protocol market data from paid API", "url": "https://api.example.com/defi/protocols"},
            {"amount": 0.01, "to": "0x742d35Cc6634C0532925a3b8D4C9C3E0a1b2f3A4", "reason": "Fetch DeFi protocol market data from paid API", "url": "https://api.example.com/defi/protocols"},
            {"amount": 0.01, "to": "0x742d35Cc6634C0532925a3b8D4C9C3E0a1b2f3A4", "reason": "Fetch DeFi protocol market data from paid API", "url": "https://api.example.com/defi/protocols"},
            {"amount": 0.03, "to": "0x742d35Cc6634C0532925a3b8D4C9C3E0a1b2f3A4", "reason": "Fetch DeFi protocol market data from paid API", "url": "https://api.example.com/defi/protocols"},  # exceeds remaining → BLOCK
        ],
    },
    {
        "name": "Quick lookup",
        "budget": 0.005,
        "pays": [
            {"amount": 0.01, "to": "0x742d35Cc6634C0532925a3b8D4C9C3E0a1b2f3A4", "reason": "Expensive premium data purchase exceeding budget", "url": "https://api.example.com/premium"},  # over budget → BLOCK
        ],
    },
    {
        "name": "Automated data collection",
        "budget": 1.0,
        "pays": [
            {"amount": 0.001, "to": f"0x{'a' * 38}{i:02d}", "reason": "Pay for premium", "url": "https://api.example.com/data"}
            for i in range(10)  # velocity + low coherence → ESCALATE after a few
        ],
    },
]


def main() -> None:
    print("\n🏦 Ledge SDK — Transaction Validation Demo (loop)")
    print("   Protocol: x402  |  Network: base_testnet (mock)")
    print("   Policy: budget, velocity, coherence → ALLOW / BLOCK / ESCALATE")

    policy = load_policy("example/policy.json")
    wallet = Wallet(
        policy=policy,
        signer=MockSigner(),
        network="base_testnet",
        audit_logger=AuditLogger("./demo_mock_audit.jsonl"),
        agent_id="research-agent-01",
    )
    wallet._executors["x402"] = _MockX402Executor()

    for scenario in SCENARIOS:
        section(f"Task: {scenario['name']} (budget ${scenario['budget']:.4f})")
        with wallet.task(scenario["name"], budget=scenario["budget"]) as task:
            for i, pay in enumerate(scenario["pays"]):
                try:
                    result = task.pay(
                        amount_usd=pay["amount"],
                        to=pay["to"],
                        reason=pay["reason"],
                        endpoint_url=pay["url"],
                    )
                    remaining = next(iter(wallet.balances().values()), 0)
                    print(f"  #{i+1}  ✅ ALLOW   ${pay['amount']:.4f}  →  remaining ${remaining:.4f}  risk={result.risk_score:.2f}")
                except TransactionBlocked as e:
                    print(f"  #{i+1}  🚫 BLOCK  ${pay['amount']:.4f}  |  check={e.check_name}  |  {e.reason[:50]}")
                    break
                except TransactionEscalated as e:
                    print(f"  #{i+1}  ⚠️  ESCALATE  ${pay['amount']:.4f}  |  risk={e.risk_score:.2f}  |  {e.reason[:50]}")
                    break
                except Exception as e:
                    print(f"  #{i+1}  ❌ {e}")
                    break

    section("Audit Trail (most recent first)")
    for event in wallet.get_audit_trail(12):
        icon = {"allow": "✅", "block": "🚫", "escalate": "⚠️ "}.get(event.outcome, "?")
        print(
            f"  {icon} [{event.outcome.upper():8s}] "
            f"${event.amount_usd:.4f} USDC | "
            f"{event.decision_reason[:45]}"
        )

    print("\n📋 Audit log: ./demo_mock_audit.jsonl")
    print("   View: head -1 demo_mock_audit.jsonl | python -m json.tool\n")


if __name__ == "__main__":
    main()
