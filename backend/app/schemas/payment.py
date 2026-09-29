"""
Pydantic schemas for the /payment/process endpoint
and the Control Tower feed.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class Priority(str, Enum):
    NORMAL = "NORMAL"
    URGENT = "URGENT"
    BULK   = "BULK"


class TransactionStatus(str, Enum):
    INITIATED          = "INITIATED"
    RISK_ANALYZED      = "RISK_ANALYZED"
    COMPLIANCE_CHECKED = "COMPLIANCE_CHECKED"
    ROUTE_SELECTED     = "ROUTE_SELECTED"
    SETTLEMENT_PENDING = "SETTLEMENT_PENDING"
    SETTLED            = "SETTLED"
    FAILED             = "FAILED"
    ON_HOLD            = "ON_HOLD"


# ── Payment Request ───────────────────────────────────────────

class PaymentRequest(BaseModel):
    sender_id: str                      = Field(..., description="Corporate/institutional sender ID")
    sender_country: str                 = Field(..., min_length=2, max_length=2)
    receiver_id: str
    receiver_country: str               = Field(..., min_length=2, max_length=2)
    amount: float                       = Field(..., gt=0)
    source_currency: str                = Field(..., min_length=3, max_length=3)
    target_currency: str                = Field(..., min_length=3, max_length=3)
    priority: Priority                  = Priority.NORMAL
    account_age_days: int               = Field(365, ge=0)
    transaction_velocity_24h: int       = Field(1, ge=0)
    recipient_history_days: int         = Field(90, ge=0)
    dry_run: bool                       = False   # if True: no DB write, no blockchain


# ── Sub-responses ─────────────────────────────────────────────

class RiskSummary(BaseModel):
    score: int
    level: str
    decision: str
    top_factors: List[Dict[str, Any]]


class ComplianceSummary(BaseModel):
    passed: bool
    rules_triggered: List[str]
    notes: Optional[str] = None


class RouteScore(BaseModel):
    rail_id: str
    rail_name: str
    score: float
    eligible: bool
    ineligible_reason: Optional[str] = None


class SelectedRoute(BaseModel):
    rail_id: str
    rail_name: str
    score: float
    settlement_sec: int
    total_cost_source: float       # in source currency
    effective_rate: float
    recipient_amount: float        # in target currency
    reason: str


class BlockchainProof(BaseModel):
    network: str
    contract: str
    tx_hash: Optional[str]
    block_number: Optional[int]
    record_id: Optional[int]


class SettlementSummary(BaseModel):
    settled_at: Optional[str]
    settlement_time_ms: Optional[int]
    blockchain: Optional[BlockchainProof]


# ── Full Payment Response ─────────────────────────────────────

class PaymentResponse(BaseModel):
    transaction_ref: str
    status: TransactionStatus
    risk: RiskSummary
    compliance: ComplianceSummary
    selected_route: Optional[SelectedRoute]
    all_routes_evaluated: List[RouteScore]
    settlement: Optional[SettlementSummary]
    processing_time_ms: int


# ── Control Tower ─────────────────────────────────────────────

class ControlTowerStats(BaseModel):
    active_payments: int
    volume_source: float
    avg_settlement_sec: float
    high_risk_count: int
    on_hold_count: int
    liquidity_alerts: int
    route_changes: int
    rail_distribution: Dict[str, int]
    cost_saved_source: float


class TransactionFeedItem(BaseModel):
    ref: str
    corridor: str
    amount: float
    source_currency: str
    target_currency: str
    risk_level: str
    status: str
    rail: Optional[str]
    created_at: str
    settled_at: Optional[str]


class TransactionFeed(BaseModel):
    total: int
    page: int
    limit: int
    items: List[TransactionFeedItem]
