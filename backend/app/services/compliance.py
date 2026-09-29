"""
Compliance Engine — Phase 2
============================
Applies rule-based checks ON TOP of the ML risk score.
ML alone does not block — the rule engine makes the final call.

Rules (in priority order):
  BLOCK  — hard stops, no override
  REVIEW — human review required, no automatic settlement
  FLAG   — soft flag, logged but approved
"""

from typing import Dict, Any, List, Tuple
from dataclasses import dataclass, field

# ─────────────────────────────────────────────────────────────
# Simulated sanctions list (prototype — NOT real data)
# ─────────────────────────────────────────────────────────────

SANCTIONED_COUNTRIES = {"IR", "KP", "SY", "CU"}   # prototype simulation only

HIGH_RISK_COUNTRIES = {"RU", "NG", "PK", "BY", "MM", "VE"}

# Amount thresholds (INR equivalent, prototype values)
REVIEW_AMOUNT_THRESHOLD = 2_000_000      # ₹20 lakh → REVIEW
BLOCK_AMOUNT_THRESHOLD  = 50_000_000    # ₹5 crore → BLOCK

VELOCITY_REVIEW_THRESHOLD = 10           # >10 txns in 24h → REVIEW
VELOCITY_BLOCK_THRESHOLD  = 25           # >25 txns in 24h → BLOCK

RISK_SCORE_REVIEW_THRESHOLD = 71
RISK_SCORE_BLOCK_THRESHOLD  = 86


# ─────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────

@dataclass
class ComplianceResult:
    passed: bool
    final_decision: str              # APPROVE | REVIEW | BLOCK
    rules_triggered: List[str] = field(default_factory=list)
    block_reasons: List[str]   = field(default_factory=list)
    review_reasons: List[str]  = field(default_factory=list)
    notes: str = ""


# ─────────────────────────────────────────────────────────────
# Rule definitions
# ─────────────────────────────────────────────────────────────

def _rule_sanctions(data: Dict[str, Any]) -> Tuple[str, str]:
    """BLOCK if receiver country is sanctioned (prototype simulation)."""
    country = data.get("receiver_country", "").upper()
    if country in SANCTIONED_COUNTRIES:
        return "BLOCK", f"Receiver country '{country}' is on the simulated sanctions list"
    return "PASS", ""


def _rule_amount_limit(data: Dict[str, Any]) -> Tuple[str, str]:
    """BLOCK/REVIEW based on transaction amount."""
    amount = float(data.get("amount", 0))
    if amount >= BLOCK_AMOUNT_THRESHOLD:
        return "BLOCK", f"Amount {amount:,.0f} exceeds block threshold {BLOCK_AMOUNT_THRESHOLD:,.0f}"
    if amount >= REVIEW_AMOUNT_THRESHOLD:
        return "REVIEW", f"Amount {amount:,.0f} exceeds review threshold {REVIEW_AMOUNT_THRESHOLD:,.0f}"
    return "PASS", ""


def _rule_velocity(data: Dict[str, Any]) -> Tuple[str, str]:
    """BLOCK/REVIEW based on transaction velocity."""
    velocity = int(data.get("transaction_velocity_24h", 0))
    if velocity >= VELOCITY_BLOCK_THRESHOLD:
        return "BLOCK", f"Transaction velocity {velocity}/24h exceeds block threshold {VELOCITY_BLOCK_THRESHOLD}"
    if velocity >= VELOCITY_REVIEW_THRESHOLD:
        return "REVIEW", f"Transaction velocity {velocity}/24h exceeds review threshold {VELOCITY_REVIEW_THRESHOLD}"
    return "PASS", ""


def _rule_risk_score(data: Dict[str, Any]) -> Tuple[str, str]:
    """BLOCK/REVIEW based on ML risk score."""
    score = int(data.get("risk_score", 0))
    if score >= RISK_SCORE_BLOCK_THRESHOLD:
        return "BLOCK", f"ML risk score {score}/100 exceeds block threshold {RISK_SCORE_BLOCK_THRESHOLD}"
    if score >= RISK_SCORE_REVIEW_THRESHOLD:
        return "REVIEW", f"ML risk score {score}/100 exceeds review threshold {RISK_SCORE_REVIEW_THRESHOLD}"
    return "PASS", ""


def _rule_high_risk_corridor(data: Dict[str, Any]) -> Tuple[str, str]:
    """REVIEW if destination is a high-risk country AND amount is above ₹5L."""
    country = data.get("receiver_country", "").upper()
    amount  = float(data.get("amount", 0))
    if country in HIGH_RISK_COUNTRIES and amount >= 500_000:
        return "REVIEW", (
            f"High-risk corridor (destination: {country}) with amount {amount:,.0f} "
            f"requires enhanced due diligence"
        )
    return "PASS", ""


def _rule_new_recipient_high_amount(data: Dict[str, Any]) -> Tuple[str, str]:
    """REVIEW if recipient is new AND amount is significant."""
    hist   = int(data.get("recipient_history_days", 999))
    amount = float(data.get("amount", 0))
    if hist < 7 and amount >= 500_000:
        return "REVIEW", (
            f"New recipient (relationship: {hist} days) with large amount {amount:,.0f} "
            f"requires verification"
        )
    return "PASS", ""


# ─────────────────────────────────────────────────────────────
# All rules in evaluation order
# ─────────────────────────────────────────────────────────────

RULES = [
    ("SANCTIONS_CHECK",            _rule_sanctions),
    ("AMOUNT_LIMIT",               _rule_amount_limit),
    ("VELOCITY_CHECK",             _rule_velocity),
    ("ML_RISK_SCORE",              _rule_risk_score),
    ("HIGH_RISK_CORRIDOR",         _rule_high_risk_corridor),
    ("NEW_RECIPIENT_HIGH_AMOUNT",  _rule_new_recipient_high_amount),
]


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def run_compliance(data: Dict[str, Any]) -> ComplianceResult:
    """
    Run all compliance rules against the transaction + risk data.

    Args:
        data: merged dict of payment request + risk assessment result
              Expected keys: amount, receiver_country, transaction_velocity_24h,
                             risk_score, recipient_history_days

    Returns:
        ComplianceResult with final_decision and triggered rules
    """
    block_reasons  = []
    review_reasons = []
    triggered      = []

    for rule_name, rule_fn in RULES:
        outcome, reason = rule_fn(data)
        if outcome == "BLOCK":
            block_reasons.append(reason)
            triggered.append(rule_name)
        elif outcome == "REVIEW":
            review_reasons.append(reason)
            triggered.append(rule_name)

    # Decision hierarchy: BLOCK > REVIEW > APPROVE
    if block_reasons:
        final = "BLOCK"
        passed = False
        notes  = f"Blocked by {len(block_reasons)} rule(s). No automatic settlement."
    elif review_reasons:
        final  = "REVIEW"
        passed = False
        notes  = f"Flagged for review by {len(review_reasons)} rule(s). Requires manual approval."
    else:
        final  = "APPROVE"
        passed = True
        notes  = "All compliance checks passed."

    return ComplianceResult(
        passed=passed,
        final_decision=final,
        rules_triggered=triggered,
        block_reasons=block_reasons,
        review_reasons=review_reasons,
        notes=notes,
    )
