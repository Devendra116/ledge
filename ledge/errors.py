"""Custom exceptions. Nothing else lives here."""


class TransactionBlocked(Exception):
    def __init__(self, reason: str, check_name: str) -> None:
        self.reason = reason
        self.check_name = check_name
        super().__init__(f"[{check_name}] Blocked: {reason}")


class TransactionEscalated(Exception):
    def __init__(self, reason: str, risk_score: float) -> None:
        self.reason = reason
        self.risk_score = risk_score
        super().__init__(f"Escalated (score={risk_score:.2f}): {reason}")


class BudgetExceeded(TransactionBlocked):
    pass


class PolicyNotLoaded(Exception):
    pass


class SigningFailed(Exception):
    pass


class ExecutionFailed(Exception):
    pass
