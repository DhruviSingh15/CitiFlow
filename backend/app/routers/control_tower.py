"""
Control Tower Router — Phase 6
================================
GET /api/v1/control-tower/stats         — aggregate dashboard stats
GET /api/v1/control-tower/transactions  — paginated live feed
GET /api/v1/control-tower/liquidity     — current rail liquidity state
POST /api/v1/control-tower/simulate     — inject demo scenario (dry_run)
PATCH /api/v1/rails/{rail_id}/liquidity — admin: update rail liquidity
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import statistics

from app.schemas.payment import (
    ControlTowerStats, TransactionFeed, TransactionFeedItem
)
from app.schemas.fx_route import LiquidityUpdateRequest
from app.services.liquidity import get_pool_snapshot, update_liquidity
from app.routers.payment import get_all_transactions

router = APIRouter(tags=["Control Tower"])


# ─────────────────────────────────────────────────────────────
# GET /control-tower/stats
# ─────────────────────────────────────────────────────────────

@router.get("/control-tower/stats", response_model=ControlTowerStats, summary="Dashboard aggregate stats")
async def get_stats():
    """Returns live aggregate statistics for the CitiFlow Control Tower."""
    txns = get_all_transactions()

    active       = [t for t in txns.values() if t["status"] not in ("SETTLED", "FAILED")]
    high_risk    = [t for t in txns.values() if t.get("risk") and t["risk"].level == "HIGH"]
    on_hold      = [t for t in txns.values() if t["status"] == "ON_HOLD"]
    settled      = [t for t in txns.values() if t["status"] == "SETTLED"]

    # Volume
    total_volume = sum(t.get("amount", 0) for t in txns.values())

    # Average settlement time
    settle_times = []
    for t in settled:
        s = t.get("selected_route")
        if s:
            settle_times.append(s.settlement_sec)
    avg_settle = round(statistics.mean(settle_times), 1) if settle_times else 0.0

    # Rail distribution
    rail_dist: dict = {}
    for t in settled:
        r = t.get("selected_route")
        if r:
            rail_dist[r.rail_id] = rail_dist.get(r.rail_id, 0) + 1

    # Route changes (RAIL_C rejections due to liquidity → rerouted)
    route_changes = sum(
        1 for t in txns.values()
        if t.get("all_routes_evaluated") and
        any(not r.eligible for r in (t.get("all_routes_evaluated") or []))
    )

    # Cost saved vs always choosing RAIL_A (highest cost)
    cost_saved = 0.0
    for t in settled:
        s = t.get("selected_route")
        if s and s.rail_id != "RAIL_A":
            # Rough estimate: RAIL_A fee=700, selected fee varies
            cost_saved += max(700 - s.total_cost_source, 0)

    # Liquidity alerts
    pools     = get_pool_snapshot()
    liq_alerts = sum(1 for p in pools if p["alert"])

    return ControlTowerStats(
        active_payments=len(active),
        volume_source=round(total_volume, 2),
        avg_settlement_sec=avg_settle,
        high_risk_count=len(high_risk),
        on_hold_count=len(on_hold),
        liquidity_alerts=liq_alerts,
        route_changes=route_changes,
        rail_distribution=rail_dist,
        cost_saved_source=round(cost_saved, 2),
    )


# ─────────────────────────────────────────────────────────────
# GET /control-tower/transactions
# ─────────────────────────────────────────────────────────────

@router.get("/control-tower/transactions", response_model=TransactionFeed, summary="Live transaction feed")
async def get_transactions(
    page: int  = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
):
    """Paginated transaction feed for the Control Tower live view."""
    txns = list(get_all_transactions().values())

    # Most recent first
    txns.sort(key=lambda t: t.get("created_at", ""), reverse=True)

    # Filter
    if status:
        txns = [t for t in txns if str(t.get("status", "")).upper() == status.upper()]
    if risk_level:
        txns = [t for t in txns
                if t.get("risk") and t["risk"].level.upper() == risk_level.upper()]

    total = len(txns)
    start = (page - 1) * limit
    page_items = txns[start: start + limit]

    items = [
        TransactionFeedItem(
            ref=t["ref"],
            corridor=t.get("corridor", ""),
            amount=t.get("amount", 0),
            source_currency=t.get("source_currency", ""),
            target_currency=t.get("target_currency", ""),
            risk_level=t["risk"].level if t.get("risk") else "UNKNOWN",
            status=str(t.get("status", "")),
            rail=t["selected_route"].rail_id if t.get("selected_route") else None,
            created_at=t.get("created_at", ""),
            settled_at=t.get("settled_at"),
        )
        for t in page_items
    ]

    return TransactionFeed(total=total, page=page, limit=limit, items=items)


# ─────────────────────────────────────────────────────────────
# GET /control-tower/liquidity
# ─────────────────────────────────────────────────────────────

@router.get("/control-tower/liquidity", summary="Current rail liquidity state")
async def get_liquidity():
    """Returns current available liquidity for all payment rails."""
    return {"rails": get_pool_snapshot()}


# ─────────────────────────────────────────────────────────────
# PATCH /rails/{rail_id}/liquidity  — demo admin
# ─────────────────────────────────────────────────────────────

@router.patch("/rails/{rail_id}/liquidity", summary="Update rail liquidity (demo admin)")
async def patch_liquidity(rail_id: str, body: LiquidityUpdateRequest):
    """
    Admin endpoint: manually set a rail's available liquidity.
    Used in the demo to trigger Scenario C (liquidity failure rerouting).
    """
    success = update_liquidity(rail_id.upper(), body.available_amount)
    if not success:
        raise HTTPException(404, f"Rail {rail_id} not found")
    return {
        "rail_id": rail_id.upper(),
        "available_amount": body.available_amount,
        "message": f"Liquidity for {rail_id.upper()} updated to {body.available_amount:,.0f}",
    }


# ─────────────────────────────────────────────────────────────
# GET /control-tower/rails  — rail metadata
# ─────────────────────────────────────────────────────────────

@router.get("/control-tower/rails", summary="Available payment rails")
async def get_rails():
    """Returns static rail configuration for UI display."""
    return {
        "rails": [
            {
                "rail_id": "RAIL_A",
                "name": "Citi Instant",
                "type": "INSTANT",
                "fee_fixed": 700,
                "settlement_sec": 10,
                "fx_spread_bps": 80,
                "risk_level": "LOW",
                "description": "Highest fee, always available, maximum speed guarantee",
            },
            {
                "rail_id": "RAIL_B",
                "name": "Citi Standard",
                "type": "STANDARD",
                "fee_fixed": 400,
                "settlement_sec": 60,
                "fx_spread_bps": 50,
                "risk_level": "LOW",
                "description": "Balanced cost and speed, recommended for most payments",
            },
            {
                "rail_id": "RAIL_C",
                "name": "Citi Tokenized",
                "type": "TOKENIZED",
                "fee_fixed": 250,
                "settlement_sec": 3,
                "fx_spread_bps": 30,
                "risk_level": "MEDIUM",
                "description": "Tokenized DLT rail — lowest cost, fastest, liquidity-constrained",
            },
        ]
    }
