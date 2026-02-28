"""Tests for Layer 1 — technical checks."""

import os

from ledge.engine.checks.technical import (
    check_address_format,
    check_balance,
    check_simulation,
)
from ledge.engine.result import Outcome
from ledge.models import Policy, TaskContext, Transaction


def test_valid_address_passes(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    result = check_address_format(tx, ctx, policy)
    assert result.name == "address_format"
    assert result.outcome is Outcome.ALLOW


def test_invalid_address_blocked(ctx: TaskContext, policy: Policy) -> None:
    tx = Transaction(
        amount_usd=0.01,
        to="not-an-address",
        reason="Fetch data",
        task_id=ctx.task_id,
        protocol="x402",
        network="base_testnet",
    )
    result = check_address_format(tx, ctx, policy)
    assert result.outcome is Outcome.BLOCK
    assert "Invalid address" in result.reason


def test_empty_address_blocked(ctx: TaskContext, policy: Policy) -> None:
    tx = Transaction(
        amount_usd=0.01,
        to="",
        reason="Fetch data",
        task_id=ctx.task_id,
        protocol="x402",
        network="base_testnet",
    )
    result = check_address_format(tx, ctx, policy)
    assert result.outcome is Outcome.BLOCK
    assert "empty" in result.reason


def test_simulation_skipped_for_x402(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    policy.simulate_before_sign = True
    result = check_simulation(tx, ctx, policy)
    assert result.outcome is Outcome.ALLOW
    assert "Simulation skipped" in result.reason


def test_balance_skipped_without_rpc(tx: Transaction, ctx: TaskContext, policy: Policy) -> None:
    os.environ.pop("WEB3_RPC_URL", None)
    result = check_balance(tx, ctx, policy)
    assert result.outcome is Outcome.ALLOW
    assert "skipped" in result.reason
