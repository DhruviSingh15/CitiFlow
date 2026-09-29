"""
Pydantic schemas for the Risk API.
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from enum import Enum


class RiskLevel(str, Enum):
    LOW    = "LOW"
    MEDIUM = "MEDIUM"
    HIGH   = "HIGH"


class RiskDecision(str, Enum):
    APPROVE = "APPROVE"
    REVIEW  = "REVIEW"
    BLOCK   = "BLOCK"


# ── Request ──────────────────────────────────────────────────

class RiskAnalyzeRequest(BaseModel):
    amount: float                   = Field(..., gt=0, description="Transaction amount in source currency")
    transaction_velocity_24h: int   = Field(..., ge=0, description="Number of transactions sender made in last 24h")
    account_age_days: int           = Field(..., ge=0, description="Age of the sender account in days")
    recipient_history_days: int     = Field(..., ge=0, description="Days since first transaction with this recipient (0 = new)")
    country_risk_score: float       = Field(..., ge=0.0, le=1.0, description="Destination country risk (0=low, 1=high)")
    sender_country: str             = Field(..., min_length=2, max_length=2)
    receiver_country: str           = Field(..., min_length=2, max_length=2)
    amount_deviation_pct: float     = Field(0.0, description="% deviation from sender's 30-day avg (0=normal)")
    sender_balance: Optional[float] = Field(None, description="Optional: sender account balance")
    is_new_recipient: Optional[bool] = None  # auto-derived if None


# ── Response sub-models ───────────────────────────────────────

class ShapFactor(BaseModel):
    feature: str
    contribution: float
    direction: str           # "risk_increasing" | "risk_reducing"
    display_value: str       # human-readable value description


class ShapExplanation(BaseModel):
    top_factors: List[ShapFactor]
    base_value: float
    summary: str             # one-line English explanation


# ── Response ──────────────────────────────────────────────────

class RiskAnalyzeResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    risk_score: int                  # 0–100
    risk_level: RiskLevel
    decision: RiskDecision
    shap_explanation: ShapExplanation
    model_version: str = "1.0.0"
    assessed_at: str                 # ISO datetime string
