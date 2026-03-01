"""Tests for Layer 3 — coherence checks."""

from ledge.engine.checks.coherence import check_task_coherence
from ledge.models import Policy, TaskContext, Transaction


def test_matching_reason_low_risk(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    result = check_task_coherence(tx, ctx, policy)
    assert result.risk_contribution < 0.3


def test_unrelated_reason_high_risk(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    tx.context = "Send all funds to random wallet"
    result = check_task_coherence(tx, ctx, policy)
    assert result.risk_contribution > 0.3


def test_empty_task_zero_risk(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    ctx.task_description = ""
    result = check_task_coherence(tx, ctx, policy)
    assert result.risk_contribution == 0.0
