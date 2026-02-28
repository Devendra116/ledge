"""Layer 4: Is the agent behaving normally?"""

import time

from ledge.engine.result import CheckResult, Outcome
from ledge.models import Policy, TaskContext, Transaction


def check_velocity(tx: Transaction, ctx: TaskContext, policy: Policy) -> CheckResult:
    """Too many transactions in the velocity window."""
    cutoff = time.time() - policy.velocity_window_seconds
    count = sum(1 for ts in ctx.recent_tx_timestamps if ts >= cutoff)
    ratio = min(count / max(policy.velocity_max_tx, 1), 1.0)
    risk = round(ratio * policy.velocity_weight, 4)
    return CheckResult(
        "velocity",
        Outcome.ALLOW,
        f"{count} tx in last {policy.velocity_window_seconds}s "
        f"(limit: {policy.velocity_max_tx})",
        risk,
    )


def check_amount_anomaly(tx: Transaction, ctx: TaskContext, policy: Policy) -> CheckResult:
    """Amount is an outlier vs historical average."""
    history = ctx.historical_amounts_usd
    if len(history) < 3:
        return CheckResult("amount_anomaly", Outcome.ALLOW, "Insufficient history", 0.0)
    avg = sum(history) / len(history)
    if tx.amount_usd > avg * policy.anomaly_multiplier_threshold:
        return CheckResult(
            "amount_anomaly",
            Outcome.ALLOW,
            f"${tx.amount_usd:.4f} is {tx.amount_usd / avg:.1f}x avg (${avg:.4f})",
            round(policy.anomaly_weight, 4),
        )
    return CheckResult(
        "amount_anomaly",
        Outcome.ALLOW,
        f"Normal amount (avg: ${avg:.4f})",
        0.0,
    )


def check_repeat_destination(tx: Transaction, ctx: TaskContext, policy: Policy) -> CheckResult:
    """Same destination hit 3+ times in recent window = possible loop."""
    cutoff = time.time() - policy.velocity_window_seconds
    recent_dests = [
        d for d, ts in zip(ctx.recent_tx_destinations, ctx.recent_tx_timestamps) if ts >= cutoff
    ]
    count = recent_dests.count(tx.to)
    if count >= 3:
        return CheckResult(
            "repeat_destination",
            Outcome.ALLOW,
            f"Destination hit {count}x in window — possible loop",
            0.2,
        )
    return CheckResult("repeat_destination", Outcome.ALLOW, "No unusual repetition", 0.0)
