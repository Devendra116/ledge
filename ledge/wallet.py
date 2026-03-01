"""
Wallet — the single public interface for all agent payment operations.

Two usage patterns:

1. Task-scoped (multi-payment): pass budget when opening the task.
   with wallet.task("Research DeFi", budget=2.0) as task:
       result = task.pay(0.01, to="0x...", context="Fetch data", params=X402Params(url="..."))

2. Direct (single payment): optional budget (default from policy).
   result = wallet.pay(amount=0.01, to="0x...", context="...", params=X402Params(url="..."))

Executor-specific details go in params (e.g. X402Params); protocol stays at top level.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

from ledge.audit import AuditEvent, AuditLogger, make_audit_event
from ledge.engine.decision import evaluate
from ledge.engine.result import Outcome
from ledge.errors import ExecutionFailed, TransactionBlocked, TransactionEscalated
from ledge.execution.base import ExecutionResult, PaymentExecutor
from ledge.execution.x402 import X402Executor
from ledge.models import Network, Policy, TaskContext, Transaction, X402Params
from ledge.models.params import PaymentParams
from ledge.models.transaction import ContextInput, HttpMethod, Protocol
from ledge.signing.base import SigningProvider

# Prefix for direct-payment task_ids. Filter audit with task_id.startswith(DIRECT_PAY_TASK_PREFIX).
DIRECT_PAY_TASK_PREFIX = "direct"


def _params_to_endpoint(
    params: PaymentParams | None, protocol: Protocol
) -> tuple[str | None, HttpMethod, dict[str, object] | None]:
    """Unpack executor params into endpoint_url, endpoint_method, endpoint_json for Transaction."""
    if protocol == "x402" and isinstance(params, X402Params):
        return (params.url, params.method, params.body)
    return (None, "GET", None)


@dataclass
class PayResult:
    """Returned by task.pay() / wallet.pay() on success."""

    success: bool
    tx_hash: str
    amount: float
    to: str
    context: str  # string form of context given at pay time
    protocol: str
    network: str
    risk_score: float
    response_data: dict[str, object] | None = None


@dataclass
class _TaskBudget:
    """Internal budget tracker per task."""

    task_id: str
    description: str
    allocated: float
    spent: float = 0.0
    recent_tx_timestamps: list[float] = field(default_factory=list)
    recent_tx_destinations: list[str] = field(default_factory=list)
    historical_amounts_usd: list[float] = field(default_factory=list)

    @property
    def remaining(self) -> float:
        return self.allocated - self.spent

    def spend(self, amount: float, destination: str) -> None:
        import time

        self.spent += amount
        self.recent_tx_timestamps.append(time.time())
        self.recent_tx_destinations.append(destination)
        self.historical_amounts_usd.append(amount)

    def unused(self) -> float:
        return self.remaining


class _TaskSession:
    """Context manager returned by wallet.task(). What the agent interacts with."""

    def __init__(
        self,
        wallet: Wallet,
        task_id: str,
        description: str,
        budget: float,
    ) -> None:
        self._wallet = wallet
        self._task_id = task_id
        self._description = description
        self._budget = budget

    def __enter__(self) -> _TaskSession:
        self._wallet._start_task(self._task_id, self._description, self._budget)
        return self

    def __exit__(
        self, exc_type: object, exc_val: object, exc_tb: object
    ) -> Literal[False]:
        self._wallet._end_task(self._task_id)
        return False  # Never suppress exceptions

    def pay(
        self,
        amount: float,
        to: str,
        context: ContextInput,
        protocol: Protocol = "x402",
        params: PaymentParams | None = None,
    ) -> PayResult:
        """
        Make a payment. Runs full decision engine before any money moves.

        Args:
            amount:   Amount to pay
            to:       Destination address (payTo wallet address)
            context:  Agent context or current state (str or dict) — for audit and coherence
            protocol: "x402" (default) or "transfer"
            params:   Executor-specific params (e.g. X402Params(url=...) for x402)

        Returns: PayResult on success
        Raises: TransactionBlocked, TransactionEscalated, ExecutionFailed
        """
        return self._wallet._pay(
            task_id=self._task_id,
            amount=amount,
            to=to,
            context=context,
            protocol=protocol,
            params=params,
        )


class Wallet:
    """
    Main entry point. One instance per agent session.

    Usage (task-scoped, multi-payment):
        with wallet.task("Research DeFi protocols", budget=2.0) as task:
            result = task.pay(0.01, to="0x...", context="Fetch market data", params=X402Params(url="..."))

    Usage (direct, single payment):
        result = wallet.pay(amount=0.01, to="0x...", context="...", params=X402Params(url="..."))
    """

    def __init__(
        self,
        policy: Policy,
        signer: SigningProvider,
        network: Network = "base_testnet",
        audit_logger: AuditLogger | None = None,
        agent_id: str = "default-agent",
    ) -> None:
        self._policy = policy
        self._signer = signer
        self._network = network
        self._logger = audit_logger or AuditLogger()
        self._agent_id = agent_id
        self._tasks: dict[str, _TaskBudget] = {}

        self._executors: dict[str, PaymentExecutor] = {
            "x402": X402Executor(network=network),
        }

    def task(
        self,
        description: str,
        budget: float,
        task_id: str | None = None,
    ) -> _TaskSession:
        """
        Create a scoped task with a budget. Use as context manager.
        Budget is allocated on enter, unused funds logged on exit.
        """
        tid = task_id or str(uuid.uuid4())
        return _TaskSession(self, tid, description, budget)

    def pay(
        self,
        amount: float,
        to: str,
        context: ContextInput,
        protocol: Protocol = "x402",
        params: PaymentParams | None = None,
        budget: float | None = None,
        description: str | None = None,
    ) -> PayResult:
        """
        Direct single payment without task context. Convenience for one-off payments.

        Each call gets a unique task_id (direct-<uuid>) for production tracing and audit.
        Budget is optional; when omitted, uses policy max_amount_usd_per_tx for this single payment.

        Args:
            amount: Amount to pay
            to: Destination address
            context: Agent context or current state (str or dict)
            protocol: "x402" (default) or "transfer"
            params: Executor-specific params (e.g. X402Params(url=...) for x402)
            budget: Optional cap for this payment; default from policy (max_amount_usd_per_tx)
            description: Optional task description (for policy/coherence); default ""

        Returns: PayResult on success
        Raises: Same as task.pay()
        """
        task_id = f"{DIRECT_PAY_TASK_PREFIX}-{uuid.uuid4().hex}"
        effective_budget = budget if budget is not None else self._policy.max_amount_usd_per_tx
        self._start_task(task_id, description or "", effective_budget)
        try:
            return self._pay(
                task_id=task_id,
                amount=amount,
                to=to,
                context=context,
                protocol=protocol,
                params=params,
            )
        finally:
            self._end_task(task_id)

    def _start_task(self, task_id: str, description: str, budget: float) -> None:
        self._tasks[task_id] = _TaskBudget(task_id, description, budget)

    def _end_task(self, task_id: str) -> float:
        task = self._tasks.pop(task_id, None)
        return task.unused() if task else 0.0

    def _pay(
        self,
        task_id: str,
        amount: float,
        to: str,
        context: ContextInput,
        protocol: Protocol,
        params: PaymentParams | None = None,
    ) -> PayResult:
        """
        Internal payment flow:
        1. Build Transaction and TaskContext
        2. Run decision engine → Decision
        3. If BLOCK: log audit event, raise TransactionBlocked
        4. If ESCALATE: log audit event, raise TransactionEscalated
        5. If ALLOW: get executor, call execute(), get tx_hash
        6. Update task budget
        7. Log audit event
        8. Return PayResult

        Audit event is ALWAYS logged regardless of outcome.
        """
        task = self._tasks.get(task_id)
        if task is None:
            raise RuntimeError(
                f"Task '{task_id}' not found. Use wallet.task() context manager."
            )

        endpoint_url, endpoint_method, endpoint_json = _params_to_endpoint(params, protocol)
        tx = Transaction(
            amount=amount,
            to=to,
            context=context,
            task_id=task_id,
            protocol=protocol,
            network=self._network,
            endpoint_url=endpoint_url,
            endpoint_method=endpoint_method,
            endpoint_json=endpoint_json,
        )

        ctx = TaskContext(
            task_id=task_id,
            task_description=task.description,
            agent_id=self._agent_id,
            budget_allocated=task.allocated,
            budget_spent=task.spent,
            recent_tx_timestamps=task.recent_tx_timestamps.copy(),
            recent_tx_destinations=task.recent_tx_destinations.copy(),
            historical_amounts_usd=task.historical_amounts_usd.copy(),
        )

        decision = evaluate(tx, ctx, self._policy)
        tx_hash: str | None = None
        response_data: dict[str, object] | None = None

        try:
            if decision.outcome == Outcome.BLOCK:
                check_name = decision.checks[-1].name if decision.checks else "engine"
                raise TransactionBlocked(decision.reason, check_name)

            if decision.outcome == Outcome.ESCALATE:
                raise TransactionEscalated(decision.reason, decision.risk_score)

            executor = self._executors.get(tx.protocol)
            if executor is None:
                raise ExecutionFailed(
                    f"No executor registered for protocol '{tx.protocol}'"
                )

            result: ExecutionResult = executor.execute(tx, self._signer)
            tx_hash = result.tx_hash
            response_data = result.response_data
            task.spend(amount, to)

            return PayResult(
                success=True,
                tx_hash=tx_hash,
                amount=amount,
                to=to,
                context=tx.context_string,
                protocol=protocol,
                network=self._network,
                risk_score=decision.risk_score,
                response_data=response_data,
            )

        finally:
            self._logger.log(
                make_audit_event(
                    self._agent_id, task_id, task.description, tx, decision, tx_hash
                )
            )

    def get_audit_trail(self, n: int = 20) -> list[AuditEvent]:
        """Return last n audit events, most recent first."""
        return list(reversed(self._logger.recent(n)))

    def balances(self) -> dict[str, float]:
        """Current remaining budget for all active tasks."""
        return {tid: t.remaining for tid, t in self._tasks.items()}
