"""Tests for the audit logger."""

import json
import os
from pathlib import Path

from ledge.audit import AuditEvent, AuditLogger, make_audit_event
from ledge.engine.decision import evaluate
from ledge.models import Policy, TaskContext, Transaction


def _make_event(tmp_path: Path) -> tuple[AuditLogger, AuditEvent]:
    log_path = tmp_path / "test_audit.jsonl"
    logger = AuditLogger(str(log_path))
    tx = Transaction(
        amount=0.01,
        to="0x742d35Cc6634C0532925a3b8D4C9C3E0a1b2f3A4",
        context="Test payment context here",
        task_id="t1",
    )
    ctx = TaskContext("t1", "Test task", "agent-1", 10.0, 0.0)
    decision = evaluate(tx, ctx, Policy())
    event = make_audit_event("agent-1", "t1", "Test task", tx, decision, "0xhash")
    return logger, event


def test_log_creates_file(tmp_path: Path) -> None:
    logger, event = _make_event(tmp_path)
    logger.log(event)
    assert os.path.exists(logger._path)


def test_log_appends_not_overwrites(tmp_path: Path) -> None:
    logger, event = _make_event(tmp_path)
    logger.log(event)
    logger.log(event)
    with open(logger._path, encoding="utf-8") as f:
        lines = [line for line in f.readlines() if line.strip()]
    assert len(lines) == 2


def test_recent_returns_correct_count(tmp_path: Path) -> None:
    logger, event = _make_event(tmp_path)
    for _ in range(10):
        logger.log(event)
    assert len(logger.recent(5)) == 5


def test_recent_empty_if_no_file(tmp_path: Path) -> None:
    logger = AuditLogger(str(tmp_path / "nonexistent.jsonl"))
    assert logger.recent() == []


def test_event_is_valid_json(tmp_path: Path) -> None:
    logger, event = _make_event(tmp_path)
    logger.log(event)
    with open(logger._path, encoding="utf-8") as f:
        data = json.loads(f.readline())
    assert "event_id" in data
    assert "outcome" in data
    assert "amount" in data
    assert "context_given" in data
