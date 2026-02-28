# Payment Executors

Executors handle the protocol-specific details of moving money. The decision
engine knows nothing about protocols — it produces an ALLOW / BLOCK / ESCALATE
decision. If ALLOW, the `Wallet` dispatches to the correct executor.

## Adding a New Executor

1. Create `ledge/execution/your_protocol.py`
2. Subclass `PaymentExecutor`
3. Implement `async execute(tx, signer) -> ExecutionResult`
4. Register it in `Wallet(executors={"your_protocol": YourExecutor()})`

Nothing else changes — the decision engine, models, and audit layer are
completely unaware of your protocol.

## Built-in Executors

### X402Executor

Pays for HTTP resources using the [x402 protocol](https://x402.org).

- Signs an EIP-712 payload via the `SigningProvider`
- Sends the signed payment header with the HTTP request
- Returns the HTTP response body on success

### TransferExecutor (stub)

Direct on-chain USDC ERC-20 transfer. Not yet implemented.

## ExecutionResult

Every executor returns an `ExecutionResult`:

| Field          | Type             | Description                        |
|----------------|------------------|------------------------------------|
| `tx_hash`      | `str`            | On-chain transaction hash          |
| `success`      | `bool`           | Whether the execution succeeded    |
| `protocol`     | `Protocol`       | `"x402"` or `"transfer"`          |
| `amount_usd`   | `float`          | Amount that was transferred        |
| `network`      | `str`            | Network the tx executed on         |
| `raw_response` | `dict` or `None` | Protocol-specific response payload |
