"""TransferExecutor — direct EVM token transfer. Not implemented in this POC."""

from ledge.execution.base import ExecutionResult, PaymentExecutor
from ledge.models.transaction import Transaction
from ledge.signing.base import SigningProvider


class TransferExecutor(PaymentExecutor):
    """
    Direct on-chain EVM token transfer (USDC or ETH).
    Used for agent-to-agent payments or topping up wallets.

    NOT IMPLEMENTED IN POC. Raises NotImplementedError.
    Will be implemented in a future version.

    When implemented, flow will be:
      1. Build EIP-1559 tx dict with USDC transferFrom calldata
      2. Call signer.sign(tx_dict)
      3. Broadcast via web3.eth.send_raw_transaction()
      4. Wait for receipt
      5. Return ExecutionResult with on-chain tx hash
    """

    def execute(self, tx: Transaction, signer: SigningProvider) -> ExecutionResult:
        raise NotImplementedError(
            "TransferExecutor is not implemented in this version. "
            "Use X402Executor for x402 protocol payments."
        )
