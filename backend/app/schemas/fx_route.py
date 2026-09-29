"""
Pydantic schemas for FX and Route endpoints.
"""
from pydantic import BaseModel, Field
from typing import List, Optional


# ── FX ───────────────────────────────────────────────────────

class FxRequest(BaseModel):
    amount: float        = Field(..., gt=0)
    source_currency: str = Field(..., min_length=3, max_length=3)
    target_currency: str = Field(..., min_length=3, max_length=3)
    rail_id: str         = Field(..., description="Rail to apply spread from")


class FxResponse(BaseModel):
    base_rate: float
    fx_spread_bps: float
    effective_rate: float
    gross_conversion: float         # before fees
    fixed_fee: float                # flat fee in source currency
    bps_fee: float                  # basis-point fee in source currency
    total_fees_source: float
    net_recipient_amount: float     # in target currency
    source_currency: str
    target_currency: str


# ── Routes ───────────────────────────────────────────────────

class RailAvailability(BaseModel):
    rail_id: str
    name: str
    rail_type: str
    fee_fixed: float
    fee_bps: float
    settlement_sec: int
    fx_spread_bps: float
    available_liquidity: float
    reserved_liquidity: float
    liquidity_eligible: bool
    ineligible_reason: Optional[str] = None
    is_active: bool


class AvailableRailsResponse(BaseModel):
    amount: float
    source_currency: str
    target_currency: str
    rails: List[RailAvailability]
    eligible_count: int


# ── Liquidity update (admin) ──────────────────────────────────

class LiquidityUpdateRequest(BaseModel):
    available_amount: float = Field(..., ge=0)
    currency: str           = Field("INR", min_length=3, max_length=3)
