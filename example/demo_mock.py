"""
Ledge SDK — Mock demo: direct pay, group task, and failure cases (BLOCK / ESCALATE).

  python example/demo_mock.py
"""
from ledge import (
    AuditLogger,
    TransactionBlocked,
    TransactionEscalated,
    Wallet,
    load_policy,
    X402Params,
)
from ledge.execution.base import ExecutionResult, PaymentExecutor
from ledge.models.transaction import Transaction
from ledge.signing.base import SigningProvider
from ledge.signing.mock_signer import MockSigner

ADDR = "0x742d35Cc6634C0532925a3b8D4C9C3E0a1b2f3A4"
URL = "https://api.example.com/data"


class _MockExecutor(PaymentExecutor):
    def execute(self, tx: Transaction, signer: SigningProvider) -> ExecutionResult:
        return ExecutionResult(
            tx_hash=f"0xmock_{tx.amount:.4f}",
            protocol="x402",
            network=tx.network,
            amount=tx.amount,
            response_data=None,
        )


def run(wallet: Wallet) -> None:
    wallet._executors["x402"] = _MockExecutor()

    # --- 1. Direct payments ---
    print("1. Direct payments")
    print("   pay(0.01, ...) ", end="")
    r = wallet.pay(amount=0.01, to=ADDR, context="Fetch price feed", params=X402Params(url=URL))
    print(f"→ ALLOW  tx={r.tx_hash[:16]}...")

    print("   pay(1.50, ...) ", end="")
    try:
        wallet.pay(amount=1.50, to=ADDR, context="Large one-off payment", params=X402Params(url=URL))
    except TransactionBlocked as e:
        print(f"→ BLOCK  [{e.check_name}] {e.reason[:45]}")

    print("   pay(0.01, context='x') ", end="")
    try:
        wallet.pay(amount=0.01, to=ADDR, context="x", params=X402Params(url=URL))
    except TransactionBlocked as e:
        print(f"→ BLOCK  [{e.check_name}] {e.reason[:40]}")

    # --- 2. Group task: ALLOW then BLOCK (budget) ---
    print("\n2. Group task (budget 0.02)")
    with wallet.task("DeFi research", budget=0.02) as task:
        for i, amt in enumerate([0.01, 0.01, 0.01], 1):
            try:
                r = task.pay(amt, ADDR, "Fetch DeFi protocol data", params=X402Params(url=URL))
                left = next(iter(wallet.balances().values()), 0)
                print(f"   #{i} pay ${amt:.2f} → ALLOW  remaining ${left:.2f}")
            except TransactionBlocked as e:
                print(f"   #{i} pay ${amt:.2f} → BLOCK  [{e.check_name}]")
                break

    # --- 3. Group task: ESCALATE (velocity + coherence) ---
    print("\n3. Group task (velocity / coherence → ESCALATE)")
    with wallet.task("Research DeFi protocols", budget=0.10) as task:
        for i in range(6):
            try:
                r = task.pay(
                    0.005,
                    ADDR,
                    "Fetch DeFi protocol market data from paid API",
                    params=X402Params(url=URL),
                )
                print(f"   #{i+1} → ALLOW  risk={r.risk_score:.2f}")
            except TransactionEscalated as e:
                print(f"   #{i+1} → ESCALATE  risk={e.risk_score:.2f}")
                break
            except TransactionBlocked as e:
                print(f"   #{i+1} → BLOCK  [{e.check_name}]")
                break

    # --- Audit ---
    print("\n4. Audit (last 6)")
    for ev in wallet.get_audit_trail(6):
        icon = {"allow": "✅", "block": "🚫", "escalate": "⚠️"}[ev.outcome]
        print(f"   {icon} {ev.outcome:8} ${ev.amount:.4f}  {ev.decision_reason[:42]}")


def main() -> None:
    print("Ledge mock demo — direct pay, group task, BLOCK, ESCALATE\n")
    policy = load_policy("example/policy.json")
    wallet = Wallet(
        policy=policy,
        signer=MockSigner(),
        network="base_testnet",
        audit_logger=AuditLogger("./demo_mock_audit.jsonl"),
    )
    run(wallet)
    print("\nAudit file: ./demo_mock_audit.jsonl")


if __name__ == "__main__":
    main()
