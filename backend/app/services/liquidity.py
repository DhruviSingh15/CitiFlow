"""
Liquidity Service — Phase 4
============================
Manages simulated rail liquidity pools.
Checks whether a rail has enough liquidity for a given transaction amount.
Updates reserved/available amounts when payments are dispatched.

Liquidity is stored in-memory for prototype purposes.
In production this would query the rail_liquidity table in real time.
"""

import threading
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone


# ─────────────────────────────────────────────────────────────
# Simulated liquidity pools (INR amounts — prototype values)
# ─────────────────────────────────────────────────────────────

@dataclass
class LiquidityPool:
    rail_id: str
    currency: str
    available: float
    reserved: float = 0.0
    last_refreshed: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def net_available(self) -> float:
        return max(self.available - self.reserved, 0.0)


# Default pools — reset on server restart (prototype behaviour)
_DEFAULT_POOLS: Dict[str, LiquidityPool] = {
    "RAIL_A": LiquidityPool("RAIL_A", "INR", available=5_000_000.0),   # ₹50 lakh
    "RAIL_B": LiquidityPool("RAIL_B", "INR", available=2_000_000.0),   # ₹20 lakh
    "RAIL_C": LiquidityPool("RAIL_C", "INR", available=1_500_000.0),   # ₹15 lakh
}

_pools: Dict[str, LiquidityPool] = {k: v for k, v in _DEFAULT_POOLS.items()}
_lock = threading.Lock()

# Liquidity buffer — rail must have this % MORE than the tx amount
LIQUIDITY_BUFFER_PCT = 0.10   # 10%


# ─────────────────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────────────────

@dataclass
class LiquidityCheckResult:
    rail_id: str
    eligible: bool
    available_amount: float
    required_amount: float       # tx amount + buffer
    shortfall: float             # 0 if eligible
    reason: Optional[str]        # human-readable rejection reason


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def check_liquidity(rail_id: str, amount: float) -> LiquidityCheckResult:
    """
    Check whether a rail has sufficient liquidity for the given amount.

    Args:
        rail_id: e.g. "RAIL_B"
        amount:  transaction amount in source currency (INR)

    Returns:
        LiquidityCheckResult
    """
    rail_id = rail_id.upper()
    with _lock:
        pool = _pools.get(rail_id)

    if pool is None:
        return LiquidityCheckResult(
            rail_id=rail_id, eligible=False,
            available_amount=0, required_amount=amount,
            shortfall=amount,
            reason=f"Rail {rail_id} not found in liquidity registry",
        )

    required = amount * (1 + LIQUIDITY_BUFFER_PCT)
    net      = pool.net_available
    eligible = net >= required
    shortfall = max(required - net, 0.0)

    return LiquidityCheckResult(
        rail_id=rail_id,
        eligible=eligible,
        available_amount=round(net, 2),
        required_amount=round(required, 2),
        shortfall=round(shortfall, 2),
        reason=(
            None if eligible else
            f"Available {net:,.0f} < Required {required:,.0f} "
            f"(tx {amount:,.0f} + {LIQUIDITY_BUFFER_PCT*100:.0f}% buffer)"
        ),
    )


def check_all_rails(amount: float) -> Dict[str, LiquidityCheckResult]:
    """Check liquidity for all rails and return results keyed by rail_id."""
    return {
        rail_id: check_liquidity(rail_id, amount)
        for rail_id in _pools
    }


def reserve_liquidity(rail_id: str, amount: float) -> bool:
    """
    Reserve liquidity on a rail when a payment is dispatched.
    Returns True if successful, False if insufficient.
    """
    rail_id = rail_id.upper()
    with _lock:
        pool = _pools.get(rail_id)
        if not pool or pool.net_available < amount:
            return False
        pool.reserved += amount
        pool.last_refreshed = datetime.now(timezone.utc).isoformat()
        return True


def release_liquidity(rail_id: str, amount: float) -> None:
    """Release reserved liquidity after settlement completes."""
    rail_id = rail_id.upper()
    with _lock:
        pool = _pools.get(rail_id)
        if pool:
            pool.reserved = max(pool.reserved - amount, 0.0)
            pool.last_refreshed = datetime.now(timezone.utc).isoformat()


def update_liquidity(rail_id: str, available_amount: float) -> bool:
    """
    Admin endpoint: update a rail's available liquidity.
    Used for demo scenarios (e.g. simulate Rail B running low).
    """
    rail_id = rail_id.upper()
    with _lock:
        pool = _pools.get(rail_id)
        if not pool:
            return False
        pool.available = max(available_amount, 0.0)
        pool.last_refreshed = datetime.now(timezone.utc).isoformat()
        return True


def get_pool_snapshot() -> List[dict]:
    """Return current liquidity state for all rails (for Control Tower)."""
    with _lock:
        return [
            {
                "rail_id":        p.rail_id,
                "currency":       p.currency,
                "available":      p.available,
                "reserved":       p.reserved,
                "net_available":  p.net_available,
                "last_refreshed": p.last_refreshed,
                "alert":          p.net_available < 500_000,  # alert if < ₹5L
            }
            for p in _pools.values()
        ]


def reset_pools() -> None:
    """Reset all pools to defaults (for demo/testing)."""
    global _pools
    with _lock:
        _pools = {k: LiquidityPool(v.rail_id, v.currency, v.available)
                  for k, v in _DEFAULT_POOLS.items()}
