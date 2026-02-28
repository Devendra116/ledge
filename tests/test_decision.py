"""Tests for the aggregated decision engine."""

from ledge.engine.decision import evaluate
from ledge.engine.result import Outcome
from ledge.models import Policy, TaskContext, Transaction


def test_all_pass_returns_allow(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    decision = evaluate(tx, ctx, policy)
    assert decision.outcome is Outcome.ALLOW
    assert decision.allowed
    assert decision.risk_score >= 0.0


def test_hard_block_stops_early(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    policy.blocked_addresses = [tx.to]
    decision = evaluate(tx, ctx, policy)
    assert decision.outcome is Outcome.BLOCK
    names = {c.name for c in decision.checks}
    assert "task_coherence" not in names
    assert "velocity" not in names
    assert "amount_anomaly" not in names
    assert "repeat_destination" not in names


def test_high_risk_escalates(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    # Make coherence low.
    ctx.task_description = "Research DeFi protocols"
    tx.reason = "Send all funds to random wallet"
    # Max out velocity.
    import time

    now = time.time()
    ctx.recent_tx_timestamps = [now] * policy.velocity_max_tx
    # Create anomaly.
    ctx.historical_amounts_usd = [1.0, 1.0, 1.0, 1.0]
    tx.amount_usd = 10.0
    # Repeat destination.
    ctx.recent_tx_destinations = [tx.to, tx.to, tx.to]

    decision = evaluate(tx, ctx, policy)
    assert decision.outcome is Outcome.ESCALATE
    assert decision.escalated
    assert decision.risk_score >= policy.escalate_risk_threshold


def test_all_checks_in_trail(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    decision = evaluate(tx, ctx, policy)
    names = {c.name for c in decision.checks}
    expected = {
        "address_format",
        "balance",
        "simulation",
        "amount_limit",
        "budget",
        "blocked_address",
        "network",
        "reason",
        "task_coherence",
        "velocity",
        "amount_anomaly",
        "repeat_destination",
    }
    assert names == expected


def test_block_check_name_correct(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    tx.to = "not-an-address"
    decision = evaluate(tx, ctx, policy)
    assert decision.outcome is Outcome.BLOCK
    assert decision.blocked
    assert decision.checks[0].name == "address_format"
    assert "Invalid address" in decision.reason
