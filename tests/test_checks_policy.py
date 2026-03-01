"""Tests for Layer 2 — policy checks."""

from ledge.engine.checks.policy import (
    check_amount_limit,
    check_blocked_address,
    check_budget,
    check_network,
    check_reason,
)
from ledge.engine.result import Outcome
from ledge.models import Policy, TaskContext, Transaction


def test_over_limit_blocked(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    policy.max_amount_usd_per_tx = 0.0001
    result = check_amount_limit(tx, ctx, policy)
    assert result.outcome is Outcome.BLOCK
    assert "exceeds per-tx limit" in result.reason


def test_under_limit_passes(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    policy.max_amount_usd_per_tx = 1.0
    result = check_amount_limit(tx, ctx, policy)
    assert result.outcome is Outcome.ALLOW


def test_budget_exceeded_blocked(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    ctx.budget_spent = ctx.budget_allocated
    result = check_budget(tx, ctx, policy)
    assert result.outcome is Outcome.BLOCK
    assert "exceeds remaining budget" in result.reason


def test_budget_passes(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    result = check_budget(tx, ctx, policy)
    assert result.outcome is Outcome.ALLOW


def test_blocked_address(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    policy.blocked_addresses = [tx.to]
    result = check_blocked_address(tx, ctx, policy)
    assert result.outcome is Outcome.BLOCK
    assert "blocked address list" in result.reason


def test_disallowed_network(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    tx.network = "randomnet"  # type: ignore[assignment]
    result = check_network(tx, ctx, policy)
    assert result.outcome is Outcome.BLOCK
    assert "not in allowed" in result.reason


def test_short_reason_blocked(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    tx.context = "short"
    result = check_reason(tx, ctx, policy)
    assert result.outcome is Outcome.BLOCK
    assert "Context too short" in result.reason


def test_valid_reason_passes(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    result = check_reason(tx, ctx, policy)
    assert result.outcome is Outcome.ALLOW
