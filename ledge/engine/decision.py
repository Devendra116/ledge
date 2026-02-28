"""Runs all 4 layers in order. Returns a single Decision."""

from ledge.engine.checks.behavioral import (
    check_amount_anomaly,
    check_repeat_destination,
    check_velocity,
)
from ledge.engine.checks.coherence import check_task_coherence
from ledge.engine.checks.policy import (
    check_amount_limit,
    check_blocked_address,
    check_budget,
    check_network,
    check_reason,
)
from ledge.engine.checks.technical import (
    check_address_format,
    check_balance,
    check_simulation,
)
from ledge.engine.result import CheckResult, Decision, Outcome
from ledge.models import Policy, TaskContext, Transaction

_HARD = [
    check_address_format,
    check_balance,
    check_simulation,
    check_amount_limit,
    check_budget,
    check_blocked_address,
    check_network,
    check_reason,
]
_SOFT = [check_task_coherence, check_velocity, check_amount_anomaly, check_repeat_destination]


def evaluate(tx: Transaction, ctx: TaskContext, policy: Policy) -> Decision:
    """
    Run hard checks first. Return BLOCK immediately on first failure.
    Run all soft checks. Accumulate risk.
    If risk >= threshold: return ESCALATE.
    Otherwise: return ALLOW.
    Decision.checks contains every check that ran — this is the audit trail.
    """
    run: list[CheckResult] = []

    for fn in _HARD:
        result = fn(tx, ctx, policy)
        run.append(result)
        if result.outcome == Outcome.BLOCK:
            return Decision(Outcome.BLOCK, result.reason, 0.0, run)

    for fn in _SOFT:
        run.append(fn(tx, ctx, policy))

    total_risk = round(sum(r.risk_contribution for r in run), 4)

    if total_risk >= policy.escalate_risk_threshold:
        worst = max(run, key=lambda r: r.risk_contribution)
        return Decision(
            Outcome.ESCALATE,
            f"Risk {total_risk:.2f} >= {policy.escalate_risk_threshold}: {worst.reason}",
            total_risk,
            run,
        )

    return Decision(Outcome.ALLOW, "All checks passed", total_risk, run)
