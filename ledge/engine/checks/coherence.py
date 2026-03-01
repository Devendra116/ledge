"""Layer 3: Does this payment make sense for the current task?"""

from ledge.engine.result import CheckResult, Outcome
from ledge.models import Policy, TaskContext, Transaction

_STOP_WORDS = frozenset(
    [
        "the",
        "a",
        "an",
        "to",
        "for",
        "and",
        "or",
        "in",
        "of",
        "with",
        "at",
        "by",
        "from",
        "is",
        "it",
        "this",
        "that",
        "on",
        "as",
        "i",
        "my",
        "we",
        "you",
        "are",
        "be",
        "do",
        "will",
        "can",
    ]
)


def _words(text: str) -> set[str]:
    return {w.lower() for w in text.split() if len(w) > 2 and w.lower() not in _STOP_WORDS}


def check_task_coherence(tx: Transaction, ctx: TaskContext, policy: Policy) -> CheckResult:
    """
    Word-overlap score between tx.context_string and ctx.task_description.
    overlap = |task_words ∩ reason_words| / max(|task_words|, 1)
    risk    = max(0, 1 - overlap) * coherence_weight

    Zero overlap (completely unrelated) → full coherence_weight as risk.
    Empty task description → 0 risk (benefit of the doubt).
    """
    if not ctx.task_description.strip():
        return CheckResult("task_coherence", Outcome.ALLOW, "No task description", 0.0)

    task_words = _words(ctx.task_description)
    reason_words = _words(tx.context_string)

    if not task_words:
        return CheckResult("task_coherence", Outcome.ALLOW, "Task has no meaningful words", 0.0)

    overlap = len(task_words & reason_words) / len(task_words)
    risk = round(max(0.0, 1.0 - overlap) * policy.coherence_weight, 4)
    label = "Good match" if overlap >= 0.3 else f"Low overlap ({overlap:.0%})"

    return CheckResult("task_coherence", Outcome.ALLOW, f"Coherence: {label}", risk)
