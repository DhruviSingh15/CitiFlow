"""
Settlement Service — Phase 5
==============================
Dispatches a payment to the selected rail, simulates settlement delay,
and writes an on-chain audit record via the blockchain service.

The settlement simulation:
  - Waits `settlement_sec` seconds (simulated, not real)
  - For demo purposes uses asyncio.sleep so the API stays non-blocking
  - Records the blockchain tx hash in the settlement result
"""

import asyncio
import uuid
import time
import random
from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timezone

from app.services import blockchain as blockchain_svc


@dataclass
class SettlementResult:
    transaction_ref: str
    rail_id: str
    settled_amount: float
    settled_currency: str
    settlement_time_ms: int
    blockchain_tx_hash: Optional[str]
    contract_record_id: Optional[int]
    settled_at: str
    success: bool
    error: Optional[str] = None


async def settle(
    transaction_ref: str,
    sender_id: str,
    receiver_id: str,
    amount: float,
    currency: str,
    rail_id: str,
    settlement_sec: int,
) -> SettlementResult:
    """
    Simulate payment settlement on the selected rail.
    Writes an immutable record to the smart contract.

    Args:
        transaction_ref: e.g. "TXN1001"
        sender_id:       corporate sender identifier
        receiver_id:     recipient identifier
        amount:          settled amount (in target currency)
        currency:        target currency code
        rail_id:         selected rail e.g. "RAIL_B"
        settlement_sec:  simulated settlement time

    Returns:
        SettlementResult
    """
    start_ms = int(time.time() * 1000)

    # Simulate network / rail processing time
    # Use a fraction of settlement_sec for demo responsiveness
    sim_delay = min(settlement_sec * 0.1, 2.0)   # max 2 second demo wait
    await asyncio.sleep(sim_delay)

    # Add realistic jitter (±10%)
    actual_ms = int(settlement_sec * 1000 * random.uniform(0.90, 1.10))

    # Write on-chain audit record
    tx_hash    = None
    record_id  = None
    bc_error   = None

    try:
        tx_hash, record_id = await blockchain_svc.record_settlement(
            tx_ref=transaction_ref,
            sender=sender_id,
            recipient=receiver_id,
            amount_units=int(amount * 100),   # store as smallest unit (paise/cents)
            currency=currency,
            rail=rail_id,
        )
    except Exception as e:
        bc_error = str(e)
        # Blockchain failure does NOT fail the settlement — it's an audit layer
        # In production this would trigger an alert and retry queue

    settled_at = datetime.now(timezone.utc).isoformat()

    return SettlementResult(
        transaction_ref=transaction_ref,
        rail_id=rail_id,
        settled_amount=amount,
        settled_currency=currency,
        settlement_time_ms=actual_ms,
        blockchain_tx_hash=tx_hash,
        contract_record_id=record_id,
        settled_at=settled_at,
        success=True,
        error=bc_error,   # surface blockchain error without failing settlement
    )
