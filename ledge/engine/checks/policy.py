"""Layer 2: Operator-defined hard rules. Any failure = BLOCK."""

from ledge.engine.result import CheckResult, Outcome
from ledge.models import Policy, TaskContext, Transaction


def check_amount_limit(tx: Transaction, ctx: TaskContext, policy: Policy) -> CheckResult:
    if tx.amount > policy.max_amount_usd_per_tx:
        return CheckResult(
            "amount_limit",
            Outcome.BLOCK,
            f"${tx.amount:.4f} exceeds per-tx limit of "
            f"${policy.max_amount_usd_per_tx:.4f}",
        )
    return CheckResult("amount_limit", Outcome.ALLOW, "Within per-tx limit")


def check_budget(tx: Transaction, ctx: TaskContext, policy: Policy) -> CheckResult:
    if tx.amount > ctx.budget_remaining:
        return CheckResult(
            "budget",
            Outcome.BLOCK,
            f"${tx.amount:.4f} exceeds remaining budget of "
            f"${ctx.budget_remaining:.4f}",
        )
    return CheckResult("budget", Outcome.ALLOW, f"${ctx.budget_remaining:.4f} remaining")


def check_blocked_address(tx: Transaction, ctx: TaskContext, policy: Policy) -> CheckResult:
    if tx.to.lower() in [a.lower() for a in policy.blocked_addresses]:
        return CheckResult(
            "blocked_address",
            Outcome.BLOCK,
            f"{tx.to[:20]}... is on the blocked address list",
        )
    return CheckResult("blocked_address", Outcome.ALLOW, "Address not blocked")


def check_network(tx: Transaction, ctx: TaskContext, policy: Policy) -> CheckResult:
    if tx.network not in policy.allowed_networks:
        return CheckResult(
            "network",
            Outcome.BLOCK,
            f"Network '{tx.network}' not in allowed: {policy.allowed_networks}",
        )
    return CheckResult("network", Outcome.ALLOW, f"Network '{tx.network}' allowed")


def check_reason(tx: Transaction, ctx: TaskContext, policy: Policy) -> CheckResult:
    if not policy.require_reason:
        return CheckResult("reason", Outcome.ALLOW, "Context not required")
    s = tx.context_string.strip()
    if not s or len(s) < policy.min_reason_length:
        return CheckResult(
            "reason",
            Outcome.BLOCK,
            f"Context too short ({len(s)} chars, min {policy.min_reason_length})",
        )
    return CheckResult("reason", Outcome.ALLOW, "Context provided")
