import pytest

from ledge.models import Policy, TaskContext, Transaction


@pytest.fixture
def policy() -> Policy:
    return Policy()


@pytest.fixture
def ctx() -> TaskContext:
    return TaskContext(
        task_id="t1",
        task_description="Research DeFi protocols and fetch market data",
        agent_id="agent-1",
        budget_allocated=10.0,
        budget_spent=0.0,
    )


@pytest.fixture
def tx() -> Transaction:
    return Transaction(
        amount_usd=0.01,
        to="0x742d35Cc6634C0532925a3b8D4C9C3E0a1b2f3A4",
        reason="Fetch DeFi market data from API provider",
        task_id="t1",
        protocol="x402",
        network="base_testnet",
    )
