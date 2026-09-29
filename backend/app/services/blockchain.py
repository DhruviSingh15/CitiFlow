"""
Blockchain Service — Phase 5
==============================
Interfaces with the CrossBorderSettlement.sol smart contract
deployed on a local Hardhat node.

If the Hardhat node is not running or the contract is not deployed,
all blockchain calls fail gracefully — settlement still succeeds,
but the blockchain_tx_hash will be None.

This is intentional: the blockchain layer is an AUDIT trail,
not a prerequisite for payment settlement.
"""

import json
import asyncio
from pathlib import Path
from typing import Optional, Tuple

from app.config import get_settings

# ── ABI for CrossBorderSettlement.sol ────────────────────────
# Minimal ABI — only the functions we call
CONTRACT_ABI = [
    {
        "inputs": [
            {"name": "txRef",        "type": "string"},
            {"name": "sender",       "type": "string"},
            {"name": "recipient",    "type": "string"},
            {"name": "amount",       "type": "uint256"},
            {"name": "currency",     "type": "string"},
            {"name": "rail",         "type": "string"},
            {"name": "metadataHash", "type": "string"},
        ],
        "name": "createSettlement",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "id",        "type": "uint256"},
            {"name": "newStatus", "type": "uint8"},
        ],
        "name": "updateStatus",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "id", "type": "uint256"}],
        "name": "getSettlement",
        "outputs": [
            {
                "components": [
                    {"name": "id",            "type": "uint256"},
                    {"name": "transactionRef","type": "string"},
                    {"name": "sender",        "type": "string"},
                    {"name": "recipient",     "type": "string"},
                    {"name": "amount",        "type": "uint256"},
                    {"name": "currency",      "type": "string"},
                    {"name": "selectedRail",  "type": "string"},
                    {"name": "status",        "type": "uint8"},
                    {"name": "timestamp",     "type": "uint256"},
                    {"name": "metadataHash",  "type": "string"},
                ],
                "name": "",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


def _get_web3():
    """Lazy-load Web3 connection to the Hardhat node."""
    from web3 import Web3
    settings = get_settings()
    w3 = Web3(Web3.HTTPProvider(settings.web3_provider_url))
    return w3


def _get_contract(w3):
    settings = get_settings()
    addr = settings.contract_address
    if addr == "0x0000000000000000000000000000000000000000":
        raise ValueError("Contract not deployed. Run `npx hardhat run scripts/deploy.js` first.")
    from web3 import Web3
    return w3.eth.contract(address=Web3.to_checksum_address(addr), abi=CONTRACT_ABI)


async def record_settlement(
    tx_ref: str,
    sender: str,
    recipient: str,
    amount_units: int,
    currency: str,
    rail: str,
    metadata_hash: str = "",
) -> Tuple[Optional[str], Optional[int]]:
    """
    Write a settlement record to the smart contract.

    Returns:
        (tx_hash, on_chain_record_id) or raises on failure
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        _write_to_chain,
        tx_ref, sender, recipient, amount_units, currency, rail, metadata_hash
    )
    return result


def _write_to_chain(
    tx_ref, sender, recipient, amount_units, currency, rail, metadata_hash
) -> Tuple[str, int]:
    """Synchronous Web3 call — run in executor to avoid blocking event loop."""
    from web3 import Web3

    settings = get_settings()
    w3 = _get_web3()

    if not w3.is_connected():
        raise ConnectionError("Hardhat node not reachable at " + settings.web3_provider_url)

    contract = _get_contract(w3)
    account  = w3.eth.account.from_key(settings.contract_owner_private_key)

    tx = contract.functions.createSettlement(
        tx_ref, sender, recipient,
        amount_units, currency, rail,
        metadata_hash or ""
    ).build_transaction({
        "from":     account.address,
        "nonce":    w3.eth.get_transaction_count(account.address),
        "gas":      300_000,
        "gasPrice": w3.to_wei("1", "gwei"),
    })

    signed  = w3.eth.account.sign_transaction(tx, private_key=settings.contract_owner_private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

    # Decode return value (record ID) from receipt logs
    record_id_event = contract.events.SettlementCreated().process_receipt(receipt)
    record_id = record_id_event[0]["args"]["id"] if record_id_event else None

    return tx_hash.hex(), record_id


async def get_settlement_record(record_id: int) -> Optional[dict]:
    """Fetch a settlement record from the contract by ID."""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _read_from_chain, record_id)
        return result
    except Exception:
        return None


def _read_from_chain(record_id: int) -> dict:
    w3 = _get_web3()
    contract = _get_contract(w3)
    rec = contract.functions.getSettlement(record_id).call()
    status_map = ["CREATED", "RISK_APPROVED", "ROUTE_SELECTED",
                  "SETTLEMENT_PENDING", "SETTLED", "FAILED"]
    return {
        "id":             rec[0],
        "transaction_ref": rec[1],
        "sender":         rec[2],
        "recipient":      rec[3],
        "amount":         rec[4],
        "currency":       rec[5],
        "rail":           rec[6],
        "status":         status_map[rec[7]] if rec[7] < len(status_map) else str(rec[7]),
        "timestamp":      rec[8],
        "metadata_hash":  rec[9],
    }
