"""
FX Engine — Phase 3
====================
Calculates the effective exchange rate, fees, and recipient amount
for a given source→target currency pair on a specific payment rail.

FX rates are mock/simulated values updated in-memory every 30 seconds.
In production these would come from a live FX data provider.
"""

import time
import random
from typing import Dict, Any, Optional
from dataclasses import dataclass

# ─────────────────────────────────────────────────────────────
# Mock FX mid-market rates (INR base — prototype simulation only)
# ─────────────────────────────────────────────────────────────

_BASE_RATES: Dict[str, float] = {
    "INR_SGD": 0.01600,
    "INR_USD": 0.01198,
    "INR_GBP": 0.00943,
    "INR_AED": 0.04399,
    "INR_EUR": 0.01101,
    "INR_JPY": 1.79500,
    "INR_AUD": 0.01838,
    "INR_CAD": 0.01636,
    "INR_CNY": 0.08692,
    "INR_CHF": 0.01071,
    "SGD_INR": 62.500,
    "USD_INR": 83.500,
    "GBP_INR": 106.000,
    "AED_INR": 22.730,
    "EUR_INR": 90.800,
    # Same currency
    "INR_INR": 1.0,
    "USD_USD": 1.0,
    "SGD_SGD": 1.0,
}

_last_refresh: float = 0.0
_live_rates:   Dict[str, float] = {}
REFRESH_INTERVAL = 30  # seconds


def _refresh_rates() -> None:
    """Apply small random walk to simulate live FX movement (±0.15%)."""
    global _last_refresh, _live_rates
    now = time.time()
    if now - _last_refresh < REFRESH_INTERVAL and _live_rates:
        return
    _live_rates = {
        pair: rate * (1 + random.uniform(-0.0015, 0.0015))
        for pair, rate in _BASE_RATES.items()
    }
    _last_refresh = now


def get_rate(source: str, target: str) -> float:
    """Return current mid-market rate for source→target."""
    _refresh_rates()
    key = f"{source.upper()}_{target.upper()}"
    if key in _live_rates:
        return _live_rates[key]
    # Try inverse
    inv = f"{target.upper()}_{source.upper()}"
    if inv in _live_rates:
        return 1.0 / _live_rates[inv]
    raise ValueError(f"FX rate not available for {source}→{target}")


# ─────────────────────────────────────────────────────────────
# Rail fee schedule (must stay in sync with payment_rails table)
# ─────────────────────────────────────────────────────────────

RAIL_FEES: Dict[str, Dict[str, float]] = {
    "RAIL_A": {"fee_fixed": 700.0,  "fee_bps": 0.0,  "fx_spread_bps": 80.0},
    "RAIL_B": {"fee_fixed": 400.0,  "fee_bps": 0.0,  "fx_spread_bps": 50.0},
    "RAIL_C": {"fee_fixed": 250.0,  "fee_bps": 0.0,  "fx_spread_bps": 30.0},
}


# ─────────────────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────────────────

@dataclass
class FxResult:
    source_currency: str
    target_currency: str
    rail_id: str
    base_rate: float
    fx_spread_bps: float
    effective_rate: float        # base_rate adjusted for spread
    gross_conversion: float      # amount * effective_rate (before fees)
    fixed_fee: float             # flat fee in source currency
    bps_fee: float               # basis-point fee in source currency
    total_fees_source: float     # total fees in source currency
    net_recipient_amount: float  # final amount received in target currency
    total_cost_source: float     # fees + FX loss vs mid-market in source currency


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def calculate_fx(
    amount: float,
    source_currency: str,
    target_currency: str,
    rail_id: str,
) -> FxResult:
    """
    Calculate full FX conversion for a given rail.

    Args:
        amount: transaction amount in source currency
        source_currency: e.g. "INR"
        target_currency: e.g. "SGD"
        rail_id: e.g. "RAIL_B"

    Returns:
        FxResult with all cost components
    """
    rail_fees = RAIL_FEES.get(rail_id.upper())
    if rail_fees is None:
        raise ValueError(f"Unknown rail: {rail_id}")

    base_rate      = get_rate(source_currency, target_currency)
    spread_bps     = rail_fees["fx_spread_bps"]
    # Spread widens against the customer (bank keeps the margin)
    effective_rate = base_rate * (1 - spread_bps / 10_000)

    gross_conversion = amount * effective_rate

    fixed_fee = rail_fees["fee_fixed"]
    bps_fee   = amount * (rail_fees["fee_bps"] / 10_000)
    total_fees_source = fixed_fee + bps_fee

    # Deduct fees from gross (fees charged in source currency)
    amount_after_fees = amount - total_fees_source
    net_recipient     = max(amount_after_fees * effective_rate, 0.0)

    # Total economic cost = fees + FX spread loss (vs mid-market)
    mid_market_recv   = amount * base_rate
    fx_loss_source    = (mid_market_recv - net_recipient) / base_rate if base_rate else 0
    total_cost_source = total_fees_source + max(fx_loss_source - total_fees_source, 0)

    return FxResult(
        source_currency=source_currency.upper(),
        target_currency=target_currency.upper(),
        rail_id=rail_id.upper(),
        base_rate=round(base_rate, 8),
        fx_spread_bps=spread_bps,
        effective_rate=round(effective_rate, 8),
        gross_conversion=round(gross_conversion, 4),
        fixed_fee=round(fixed_fee, 4),
        bps_fee=round(bps_fee, 4),
        total_fees_source=round(total_fees_source, 4),
        net_recipient_amount=round(net_recipient, 4),
        total_cost_source=round(total_fees_source, 4),  # simplified: fees only
    )


def compare_rails(
    amount: float,
    source_currency: str,
    target_currency: str,
    rail_ids: Optional[list] = None,
) -> Dict[str, FxResult]:
    """Return FxResult for each rail, keyed by rail_id."""
    if rail_ids is None:
        rail_ids = list(RAIL_FEES.keys())
    return {
        rail_id: calculate_fx(amount, source_currency, target_currency, rail_id)
        for rail_id in rail_ids
    }
