"""Tests for Layer 4 — behavioral checks."""

import time

from ledge.engine.checks.behavioral import (
    check_amount_anomaly,
    check_repeat_destination,
    check_velocity,
)
from ledge.models import Policy, TaskContext, Transaction


def test_no_recent_tx_zero_velocity(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    ctx.recent_tx_timestamps = []
    result = check_velocity(tx, ctx, policy)
    assert result.risk_contribution == 0.0


def test_velocity_at_limit(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    now = time.time()
    ctx.recent_tx_timestamps = [now] * policy.velocity_max_tx
    result = check_velocity(tx, ctx, policy)
    assert result.risk_contribution == policy.velocity_weight


def test_no_history_zero_anomaly(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    ctx.historical_amounts_usd = []
    result = check_amount_anomaly(tx, ctx, policy)
    assert result.risk_contribution == 0.0


def test_outlier_amount_flagged(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    ctx.historical_amounts_usd = [1.0, 1.0, 1.0, 1.0]
    tx.amount = 10.0
    result = check_amount_anomaly(tx, ctx, policy)
    assert result.risk_contribution == policy.anomaly_weight


def test_repeat_destination_flagged(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    now = time.time()
    ctx.recent_tx_destinations = [tx.to, tx.to, tx.to]
    ctx.recent_tx_timestamps = [now, now, now]
    result = check_repeat_destination(tx, ctx, policy)
    assert result.risk_contribution > 0.0
    assert "Destination hit" in result.reason
