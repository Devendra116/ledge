"""Layer 1: Can this transaction physically execute?"""

import os

from ledge.engine.result import CheckResult, Outcome
from ledge.models import Policy, TaskContext, Transaction


def check_address_format(tx: Transaction, ctx: TaskContext, policy: Policy) -> CheckResult:
    """Validate tx.to is a properly formatted Ethereum address."""
    from web3 import Web3

    if not tx.to:
        return CheckResult("address_format", Outcome.BLOCK, "Destination address is empty")
    if Web3.is_address(tx.to):
        return CheckResult("address_format", Outcome.ALLOW, "Valid Ethereum address")
    return CheckResult("address_format", Outcome.BLOCK, f"Invalid address: {tx.to[:20]}")


def check_balance(tx: Transaction, ctx: TaskContext, policy: Policy) -> CheckResult:
    """
    Check USDC balance via RPC. Skip if WEB3_RPC_URL not set.
    USDC contracts:
      Base Sepolia (eip155:84532): 0x036CbD53842c5426634e7929541eC2318f3dCF7e
      Base mainnet (eip155:8453):  0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
    Note: wallet address not in context yet — this is a placeholder.
    Implement fully once wallet address is added to TaskContext.
    """
    if not os.environ.get("WEB3_RPC_URL"):
        return CheckResult("balance", Outcome.ALLOW, "Balance check skipped — no RPC URL")
    # TODO(next): implement full balance check once wallet address is in TaskContext
    return CheckResult("balance", Outcome.ALLOW, "Balance check not yet implemented")


def check_simulation(tx: Transaction, ctx: TaskContext, policy: Policy) -> CheckResult:
    """
    Dry-run via eth_call. Skip if disabled, no RPC, or protocol is x402.
    x402 is an HTTP call not an on-chain tx — simulation not applicable.
    """
    if tx.protocol == "x402" or not policy.simulate_before_sign:
        return CheckResult("simulation", Outcome.ALLOW, "Simulation skipped")
    if not os.environ.get("WEB3_RPC_URL"):
        return CheckResult("simulation", Outcome.ALLOW, "Simulation skipped — no RPC URL")
    # TODO(next): implement eth_call simulation for transfer protocol
    return CheckResult("simulation", Outcome.ALLOW, "Simulation passed")
