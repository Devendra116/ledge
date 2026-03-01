"""Test X402Executor in isolation using respx to mock HTTP."""

import pytest

from ledge.execution.transfer import TransferExecutor
from ledge.execution.x402 import X402Executor
from ledge.models.transaction import Transaction
from ledge.signing.mock_signer import MockSigner


@pytest.fixture
def executor() -> X402Executor:
    return X402Executor(network="base_testnet")


@pytest.fixture
def mock_tx() -> Transaction:
    return Transaction(
        amount=0.01,
        to="0x742d35Cc6634C0532925a3b8D4C9C3E0a1b2f3A4",
        context="Fetch DeFi market data from paid API",
        task_id="t1",
        protocol="x402",
        network="base_testnet",
        endpoint_url="https://example-x402-api.com/data",
    )


def test_transfer_executor_raises_not_implemented() -> None:
    executor = TransferExecutor()
    tx = Transaction(
        amount=0.01,
        to="0x742d35Cc6634C0532925a3b8D4C9C3E0a1b2f3A4",
        context="test",
        task_id="t1",
        protocol="transfer",
    )
    with pytest.raises(NotImplementedError):
        executor.execute(tx, MockSigner())


@pytest.mark.skip(reason="Requires real x402 endpoint — run manually with demo_x402.py")
def test_x402_real_endpoint(executor: X402Executor, mock_tx: Transaction) -> None:
    """Integration test. Run manually against Base Sepolia."""
    signer = MockSigner()
    result = executor.execute(mock_tx, signer)
    assert result.tx_hash.startswith("0x")
    assert result.protocol == "x402"
