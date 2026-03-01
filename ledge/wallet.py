"""
Wallet — the single public interface for all agent payment operations.

Two usage patterns:

1. Task-scoped (multi-payment):
   with wallet.task("Research DeFi", budget=2.0) as task:
       result = task.pay(0.01, to="0x...", reason="Fetch data")
       result = task.pay(0.02, to="0x...", reason="Another call")

2. Direct (single payment):
   result = wallet.pay("Fetch data", budget=0.01, amount_usd=0.01, to="0x...", reason="...")

Direct payments get a unique task_id per call (e.g. direct-<uuid>) for production tracing.
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
from ledge.models import HttpMethod, Network, Policy, TaskContext, Transaction
from ledge.models.transaction import Protocol
from ledge.signing.base import SigningProvider

# Prefix for direct-payment task_ids. Filter audit with task_id.startswith(DIRECT_PAY_TASK_PREFIX).
DIRECT_PAY_TASK_PREFIX = "direct"


@dataclass
class PayResult:
    """Returned by task.pay() on success."""

    success: bool
    tx_hash: str
    amount_usd: float
    to: str
    reason: str
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
        amount_usd: float,
        to: str,
        reason: str,
        protocol: Protocol = "x402",
        endpoint_url: str | None = None,
        endpoint_method: HttpMethod = "GET",
        endpoint_json: dict[str, object] | None = None,
    ) -> PayResult:
        """
        Make a payment. Runs full decision engine before any money moves.

        Args:
            amount_usd:   Amount in USD (e.g. 0.01 = one cent)
            to:           Destination address (payTo wallet address)
            reason:       Why this payment is being made — required for audit
            protocol:     "x402" (default) or "transfer"
            endpoint_url: For x402: the URL being fetched (may differ from `to`)
            endpoint_method: "GET" or "POST" for x402 requests (default "GET")
            endpoint_json: For x402 POST: JSON body (Content-Type: application/json)

        Returns: PayResult on success
        Raises: TransactionBlocked if a hard policy check fails
        Raises: TransactionEscalated if risk score exceeds threshold
        Raises: ExecutionFailed if execution fails after approval
        """
        return self._wallet._pay(
            task_id=self._task_id,
            amount_usd=amount_usd,
            to=to,
            reason=reason,
            protocol=protocol,
            endpoint_url=endpoint_url,
            endpoint_method=endpoint_method,
            endpoint_json=endpoint_json,
        )


class Wallet:
    """
    Main entry point. One instance per agent session.

    Usage (task-scoped, multi-payment):
        with wallet.task("Research DeFi protocols", budget=2.0) as task:
            result = task.pay(0.01, to="0x...", reason="Fetch market data")

    Usage (direct, single payment):
        result = wallet.pay("Fetch data", budget=0.01, amount_usd=0.01, to="0x...", reason="...")
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
        description: str,
        budget: float,
        amount_usd: float,
        to: str,
        reason: str,
        protocol: Protocol = "x402",
        endpoint_url: str | None = None,
        endpoint_method: HttpMethod = "GET",
        endpoint_json: dict[str, object] | None = None,
    ) -> PayResult:
        """
        Direct single payment without task context. Convenience for one-off payments.

        Each call gets a unique task_id (direct-<uuid>) for production tracing and audit.
        Filter direct payments in audit with task_id.startswith(DIRECT_PAY_TASK_PREFIX).

        Args:
            description: Task description (used for policy/coherence checks)
            budget: Budget for this single payment (typically >= amount_usd)
            amount_usd: Amount in USD
            to: Destination address
            reason: Why this payment is being made
            protocol, endpoint_url, endpoint_method, endpoint_json: Same as task.pay()

        Returns: PayResult on success
        Raises: Same as task.pay()
        """
        task_id = f"{DIRECT_PAY_TASK_PREFIX}-{uuid.uuid4().hex}"
        self._start_task(task_id, description, budget)
        try:
            return self._pay(
                task_id=task_id,
                amount_usd=amount_usd,
                to=to,
                reason=reason,
                protocol=protocol,
                endpoint_url=endpoint_url,
                endpoint_method=endpoint_method,
                endpoint_json=endpoint_json,
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
        amount_usd: float,
        to: str,
        reason: str,
        protocol: Protocol,
        endpoint_url: str | None,
        endpoint_method: HttpMethod = "GET",
        endpoint_json: dict[str, object] | None = None,
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

        tx = Transaction(
            amount_usd=amount_usd,
            to=to,
            reason=reason,
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
            task.spend(amount_usd, to)

            return PayResult(
                success=True,
                tx_hash=tx_hash,
                amount_usd=amount_usd,
                to=to,
                reason=reason,
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
