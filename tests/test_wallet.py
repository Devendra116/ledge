"""Integration tests for Wallet. All use MockSigner — no real network."""

from pathlib import Path

import pytest

from ledge.audit import AuditLogger
from ledge.errors import TransactionBlocked
from ledge.execution.base import ExecutionResult
from ledge.models import Policy
from ledge.signing.mock_signer import MockSigner
from ledge.wallet import DIRECT_PAY_TASK_PREFIX, Wallet


@pytest.fixture
def wallet(tmp_path: Path) -> Wallet:
    return Wallet(
        policy=Policy(max_amount_usd_per_tx=1.0, max_spend_usd_per_task=5.0),
        signer=MockSigner(),
        network="base_testnet",
        audit_logger=AuditLogger(str(tmp_path / "test.jsonl")),
        agent_id="test-agent",
    )


def test_happy_path(wallet: Wallet) -> None:
    """Normal x402 payment → PayResult returned (executor mocked to avoid x402 import)."""
    mock_result = ExecutionResult(
        tx_hash="0xabc123",
        protocol="x402",
        network="base_testnet",
        amount_usd=0.01,
        response_data={"data": "ok"},
    )
    executor = wallet._executors["x402"]
    original_execute = executor.execute

    def mock_execute(tx, signer):
        return mock_result

    executor.execute = mock_execute
    try:
        with wallet.task("Test task", budget=1.0) as task:
            result = task.pay(
                0.01,
                "0x742d35Cc6634C0532925a3b8D4C9C3E0a1b2f3A4",
                "Fetch paid API data for testing",
                protocol="x402",
                endpoint_url="https://example.com/paid",
            )
        assert result.success is True
        assert result.tx_hash == "0xabc123"
        assert result.amount_usd == 0.01
    finally:
        executor.execute = original_execute


def test_direct_pay(wallet: Wallet) -> None:
    """Direct wallet.pay() without task context — uses unique task_id (direct-<uuid>)."""
    mock_result = ExecutionResult(
        tx_hash="0xdirect123",
        protocol="x402",
        network="base_testnet",
        amount_usd=0.01,
        response_data=None,
    )
    executor = wallet._executors["x402"]
    original_execute = executor.execute
    executor.execute = lambda tx, signer: mock_result
    try:
        result = wallet.pay(
            description="One-off fetch",
            budget=0.01,
            amount_usd=0.01,
            to="0x742d35Cc6634C0532925a3b8D4C9C3E0a1b2f3A4",
            reason="Direct payment test",
            protocol="x402",
            endpoint_url="https://example.com/paid",
        )
        assert result.success is True
        assert result.tx_hash == "0xdirect123"
        assert len(wallet._tasks) == 0  # Task cleaned up
    finally:
        executor.execute = original_execute


def test_direct_pay_audit_uses_unique_task_id(tmp_path: Path) -> None:
    """Direct payments get unique task_id per call (direct-<uuid>) for production tracing."""
    logger = AuditLogger(str(tmp_path / "direct_audit.jsonl"))
    w = Wallet(Policy(), MockSigner(), audit_logger=logger)
    w._executors["x402"].execute = lambda tx, signer: ExecutionResult(
        tx_hash="0x1", protocol="x402", network="base_testnet", amount_usd=0.01
    )
    addr = "0x742d35Cc6634C0532925a3b8D4C9C3E0a1b2f3A4"
    w.pay("Fetch A", budget=0.01, amount_usd=0.01, to=addr, reason="Direct payment test A")
    w.pay("Fetch B", budget=0.01, amount_usd=0.01, to=addr, reason="Direct payment test B")
    events = logger.recent(10)
    assert len(events) == 2
    task_ids = [e.task_id for e in events]
    assert len(set(task_ids)) == 2, "each direct pay must have unique task_id"
    assert all(tid.startswith(DIRECT_PAY_TASK_PREFIX + "-") for tid in task_ids)


def test_budget_exceeded_raises(wallet: Wallet) -> None:
    with wallet.task("Test task", budget=0.001) as task:
        with pytest.raises(TransactionBlocked) as exc:
            task.pay(
                1.0,
                "0x742d35Cc6634C0532925a3b8D4C9C3E0a1b2f3A4",
                "Exceeds budget test payment here",
            )
        assert "budget" in exc.value.check_name


def test_blocked_tx_writes_audit_log(tmp_path: Path) -> None:
    logger = AuditLogger(str(tmp_path / "audit.jsonl"))
    w = Wallet(Policy(), MockSigner(), audit_logger=logger)
    with w.task("Test task", budget=0.001) as task:
        try:
            task.pay(
                1.0,
                "0x742d35Cc6634C0532925a3b8D4C9C3E0a1b2f3A4",
                "This exceeds budget",
            )
        except TransactionBlocked:
            pass
    assert len(logger.recent(10)) == 1
    assert logger.recent(1)[0].outcome == "block"


def test_context_manager_closes_on_exception(wallet: Wallet) -> None:
    try:
        with wallet.task("Test", budget=5.0):
            raise RuntimeError("agent crashed")
    except RuntimeError:
        pass
    assert len(wallet._tasks) == 0


def test_balances_returns_remaining(wallet: Wallet) -> None:
    with wallet.task("task-a", budget=5.0):
        balances = wallet.balances()
        assert list(balances.values())[0] == 5.0


def test_audit_trail_returns_events(tmp_path: Path) -> None:
    logger = AuditLogger(str(tmp_path / "audit2.jsonl"))
    w = Wallet(Policy(), MockSigner(), audit_logger=logger)
    with w.task("Test", budget=0.001) as task:
        try:
            task.pay(
                100.0,
                "0x742d35Cc6634C0532925a3b8D4C9C3E0a1b2f3A4",
                "too much",
            )
        except TransactionBlocked:
            pass
    assert len(w.get_audit_trail(5)) >= 1
