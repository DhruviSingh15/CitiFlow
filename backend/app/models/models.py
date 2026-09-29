"""
ORM models for CitiFlow — all tables defined here.
SQLAlchemy 2.x mapped_column style.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Numeric, Integer, SmallInteger,
    Boolean, DateTime, Enum as SAEnum, ForeignKey, JSON, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.database import Base


# ─────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────

class TransactionStatus(str, enum.Enum):
    INITIATED           = "INITIATED"
    RISK_ANALYZED       = "RISK_ANALYZED"
    COMPLIANCE_CHECKED  = "COMPLIANCE_CHECKED"
    ROUTE_SELECTED      = "ROUTE_SELECTED"
    SETTLEMENT_PENDING  = "SETTLEMENT_PENDING"
    SETTLED             = "SETTLED"
    FAILED              = "FAILED"
    ON_HOLD             = "ON_HOLD"


class TransactionPriority(str, enum.Enum):
    NORMAL = "NORMAL"
    URGENT = "URGENT"
    BULK   = "BULK"


class RiskLevel(str, enum.Enum):
    LOW    = "LOW"
    MEDIUM = "MEDIUM"
    HIGH   = "HIGH"


class RiskDecision(str, enum.Enum):
    APPROVE = "APPROVE"
    REVIEW  = "REVIEW"
    BLOCK   = "BLOCK"


class RailType(str, enum.Enum):
    INSTANT   = "INSTANT"
    STANDARD  = "STANDARD"
    TOKENIZED = "TOKENIZED"


class SettlementStatus(str, enum.Enum):
    CREATED            = "CREATED"
    RISK_APPROVED      = "RISK_APPROVED"
    ROUTE_SELECTED     = "ROUTE_SELECTED"
    SETTLEMENT_PENDING = "SETTLEMENT_PENDING"
    SETTLED            = "SETTLED"
    FAILED             = "FAILED"


# ─────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────
# Tables
# ─────────────────────────────────────────────────────────────

class Transaction(Base):
    __tablename__ = "transactions"

    id               = Column(String(36), primary_key=True, default=new_uuid)
    reference        = Column(String(20), unique=True, nullable=False, index=True)
    sender_id        = Column(String(100), nullable=False)
    sender_country   = Column(String(2), nullable=False)
    receiver_id      = Column(String(100), nullable=False)
    receiver_country = Column(String(2), nullable=False)
    amount           = Column(Numeric(20, 4), nullable=False)
    source_currency  = Column(String(3), nullable=False)
    target_currency  = Column(String(3), nullable=False)
    priority         = Column(SAEnum(TransactionPriority), default=TransactionPriority.NORMAL)
    status           = Column(SAEnum(TransactionStatus), default=TransactionStatus.INITIATED)
    created_at       = Column(DateTime(timezone=True), default=utcnow)
    updated_at       = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    risk_assessment  = relationship("RiskAssessment", back_populates="transaction", uselist=False)
    route_decision   = relationship("RouteDecision",  back_populates="transaction", uselist=False)
    settlement       = relationship("Settlement",     back_populates="transaction", uselist=False)
    audit_logs       = relationship("AuditLog",       back_populates="transaction")
    fx_snapshots     = relationship("FxSnapshot",     back_populates="transaction")


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id             = Column(String(36), primary_key=True, default=new_uuid)
    transaction_id = Column(String(36), ForeignKey("transactions.id"), nullable=False, index=True)
    risk_score     = Column(SmallInteger, nullable=False)        # 0–100
    risk_level     = Column(SAEnum(RiskLevel), nullable=False)
    decision       = Column(SAEnum(RiskDecision), nullable=False)
    ml_features    = Column(JSON)                               # input snapshot
    shap_values    = Column(JSON)                               # top-5 contributors
    rule_triggers  = Column(JSON)                               # compliance rules fired
    assessed_at    = Column(DateTime(timezone=True), default=utcnow)

    transaction    = relationship("Transaction", back_populates="risk_assessment")


class PaymentRail(Base):
    __tablename__ = "payment_rails"

    id              = Column(String(10), primary_key=True)   # e.g. RAIL_A
    name            = Column(String(50), nullable=False)
    rail_type       = Column(SAEnum(RailType), nullable=False)
    fee_fixed       = Column(Numeric(10, 4), nullable=False)  # flat fee in INR
    fee_bps         = Column(Numeric(6, 4), default=0)        # basis points of amount
    settlement_sec  = Column(SmallInteger, nullable=False)
    fx_spread_bps   = Column(Numeric(6, 4), nullable=False)
    risk_level      = Column(SAEnum(RiskLevel), default=RiskLevel.LOW)
    is_active       = Column(Boolean, default=True)
    updated_at      = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    liquidity_pools = relationship("RailLiquidity", back_populates="rail")
    route_decisions = relationship("RouteDecision", back_populates="selected_rail")
    settlements     = relationship("Settlement",    back_populates="rail")


class RailLiquidity(Base):
    __tablename__ = "rail_liquidity"

    id               = Column(String(36), primary_key=True, default=new_uuid)
    rail_id          = Column(String(10), ForeignKey("payment_rails.id"), nullable=False)
    currency         = Column(String(3), nullable=False)
    available_amount = Column(Numeric(20, 4), nullable=False)
    reserved_amount  = Column(Numeric(20, 4), default=0)
    last_refreshed   = Column(DateTime(timezone=True), default=utcnow)

    rail             = relationship("PaymentRail", back_populates="liquidity_pools")


class RouteDecision(Base):
    __tablename__ = "route_decisions"

    id               = Column(String(36), primary_key=True, default=new_uuid)
    transaction_id   = Column(String(36), ForeignKey("transactions.id"), nullable=False, index=True)
    selected_rail_id = Column(String(10), ForeignKey("payment_rails.id"), nullable=False)
    scoring_matrix   = Column(JSON)                 # all rails + scores
    total_cost       = Column(Numeric(20, 4))
    effective_rate   = Column(Numeric(20, 8))
    recipient_amount = Column(Numeric(20, 4))
    routing_weights  = Column(JSON)                 # weights snapshot
    reason           = Column(Text)                 # human-readable explanation
    decided_at       = Column(DateTime(timezone=True), default=utcnow)

    transaction      = relationship("Transaction", back_populates="route_decision")
    selected_rail    = relationship("PaymentRail", back_populates="route_decisions")


class Settlement(Base):
    __tablename__ = "settlements"

    id                  = Column(String(36), primary_key=True, default=new_uuid)
    transaction_id      = Column(String(36), ForeignKey("transactions.id"), nullable=False, index=True)
    rail_id             = Column(String(10), ForeignKey("payment_rails.id"), nullable=False)
    settled_amount      = Column(Numeric(20, 4))
    settled_currency    = Column(String(3))
    settlement_time_ms  = Column(Integer)
    blockchain_tx_hash  = Column(String(100))
    contract_record_id  = Column(Integer)
    settled_at          = Column(DateTime(timezone=True))

    transaction         = relationship("Transaction", back_populates="settlement")
    rail                = relationship("PaymentRail", back_populates="settlements")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id             = Column(String(36), primary_key=True, default=new_uuid)
    transaction_id = Column(String(36), ForeignKey("transactions.id"), nullable=False, index=True)
    event          = Column(String(100), nullable=False)
    actor          = Column(String(50), default="SYSTEM")
    payload        = Column(JSON)
    timestamp      = Column(DateTime(timezone=True), default=utcnow)

    transaction    = relationship("Transaction", back_populates="audit_logs")


class FxSnapshot(Base):
    __tablename__ = "fx_snapshots"

    id                   = Column(String(36), primary_key=True, default=new_uuid)
    transaction_id       = Column(String(36), ForeignKey("transactions.id"), nullable=False, index=True)
    source_currency      = Column(String(3), nullable=False)
    target_currency      = Column(String(3), nullable=False)
    base_rate            = Column(Numeric(20, 8), nullable=False)
    spread_bps           = Column(Numeric(6, 4))
    effective_rate       = Column(Numeric(20, 8))
    gross_amount         = Column(Numeric(20, 4))
    fees_deducted        = Column(Numeric(20, 4))
    net_recipient_amount = Column(Numeric(20, 4))
    snapped_at           = Column(DateTime(timezone=True), default=utcnow)

    transaction          = relationship("Transaction", back_populates="fx_snapshots")
