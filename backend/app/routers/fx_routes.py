"""
FX + Routes Router — Phase 5
"""
from fastapi import APIRouter, Query, HTTPException
from app.schemas.fx_route import FxRequest, FxResponse, AvailableRailsResponse, RailAvailability
from app.services.fx_engine import calculate_fx, RAIL_FEES
from app.services.liquidity import check_liquidity, get_pool_snapshot

router = APIRouter(tags=["FX & Routes"])


@router.post("/fx/calculate", response_model=FxResponse, summary="Calculate FX for a rail")
async def fx_calculate(request: FxRequest):
    """Calculate effective FX rate, fees and recipient amount for a specific rail."""
    try:
        result = calculate_fx(
            request.amount,
            request.source_currency,
            request.target_currency,
            request.rail_id,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))

    return FxResponse(
        base_rate=result.base_rate,
        fx_spread_bps=result.fx_spread_bps,
        effective_rate=result.effective_rate,
        gross_conversion=result.gross_conversion,
        fixed_fee=result.fixed_fee,
        bps_fee=result.bps_fee,
        total_fees_source=result.total_fees_source,
        net_recipient_amount=result.net_recipient_amount,
        source_currency=result.source_currency,
        target_currency=result.target_currency,
    )


@router.get("/routes/available", response_model=AvailableRailsResponse, summary="Available rails for a corridor")
async def get_available_routes(
    source_currency: str = Query(..., min_length=3, max_length=3),
    target_currency: str = Query(..., min_length=3, max_length=3),
    amount: float        = Query(..., gt=0),
):
    """
    Returns all payment rails with current liquidity status for a given corridor.
    Used by the frontend to display route options before submitting a payment.
    """
    rails = []
    eligible_count = 0

    for rail_id, fees in RAIL_FEES.items():
        liq = check_liquidity(rail_id, amount)
        if liq.eligible:
            eligible_count += 1
        rails.append(RailAvailability(
            rail_id=rail_id,
            name={"RAIL_A": "Citi Instant", "RAIL_B": "Citi Standard", "RAIL_C": "Citi Tokenized"}.get(rail_id, rail_id),
            rail_type={"RAIL_A": "INSTANT", "RAIL_B": "STANDARD", "RAIL_C": "TOKENIZED"}.get(rail_id, "UNKNOWN"),
            fee_fixed=fees["fee_fixed"],
            fee_bps=fees["fee_bps"],
            settlement_sec={"RAIL_A": 10, "RAIL_B": 60, "RAIL_C": 3}.get(rail_id, 60),
            fx_spread_bps=fees["fx_spread_bps"],
            available_liquidity=liq.available_amount,
            reserved_liquidity=0.0,
            liquidity_eligible=liq.eligible,
            ineligible_reason=liq.reason,
            is_active=True,
        ))

    return AvailableRailsResponse(
        amount=amount,
        source_currency=source_currency.upper(),
        target_currency=target_currency.upper(),
        rails=rails,
        eligible_count=eligible_count,
    )
