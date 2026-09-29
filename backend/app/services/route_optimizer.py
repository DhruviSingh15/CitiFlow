"""
Route Optimizer — Phase 4
==========================
Scores all eligible payment rails and selects the optimal one.
Eligibility = rail is active AND has sufficient liquidity.

Scoring is a weighted sum of 5 normalized sub-scores:
  cost_score      — lower total cost is better
  speed_score     — faster settlement is better
  fx_score        — better effective FX rate is better
  risk_score      — lower rail risk profile is better
  liquidity_score — more headroom above requirement is better

Weights vary by transaction priority:
  NORMAL  30% cost  25% speed  20% fx  15% risk  10% liquidity
  URGENT  15% cost  40% speed  15% fx  20% risk  10% liquidity
  BULK    35% cost  10% speed  25% fx  15% risk  15% liquidity
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from app.services.fx_engine import FxResult
from app.services.liquidity import LiquidityCheckResult


# ─────────────────────────────────────────────────────────────
# Weight profiles
# ─────────────────────────────────────────────────────────────

WEIGHT_PROFILES: Dict[str, Dict[str, float]] = {
    "NORMAL": {"cost": 0.30, "speed": 0.25, "fx": 0.20, "risk": 0.15, "liquidity": 0.10},
    "URGENT": {"cost": 0.15, "speed": 0.40, "fx": 0.15, "risk": 0.20, "liquidity": 0.10},
    "BULK":   {"cost": 0.35, "speed": 0.10, "fx": 0.25, "risk": 0.15, "liquidity": 0.15},
}

# Rail risk profile scores (lower rail risk → higher risk_score)
RAIL_RISK_SCORES: Dict[str, float] = {
    "RAIL_A": 1.0,    # LOW risk rail
    "RAIL_B": 1.0,    # LOW risk rail
    "RAIL_C": 0.7,    # MEDIUM risk rail
}

# Rail settlement times in seconds
RAIL_SETTLEMENT_SEC: Dict[str, int] = {
    "RAIL_A": 10,
    "RAIL_B": 60,
    "RAIL_C": 3,
}


# ─────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────

@dataclass
class RailScore:
    rail_id: str
    rail_name: str
    eligible: bool
    ineligible_reason: Optional[str]
    score: float                        # 0–100 composite
    cost_score: float
    speed_score: float
    fx_score: float
    risk_score: float
    liquidity_score: float
    total_cost_source: float
    settlement_sec: int
    effective_rate: float
    net_recipient_amount: float
    weights_used: Dict[str, float]


@dataclass
class RouteDecision:
    selected_rail_id: str
    selected_rail_name: str
    score: float
    settlement_sec: int
    total_cost_source: float
    effective_rate: float
    recipient_amount: float
    reason: str
    all_rails: List[RailScore] = field(default_factory=list)
    weights_used: Dict[str, float] = field(default_factory=dict)


RAIL_NAMES = {
    "RAIL_A": "Citi Instant",
    "RAIL_B": "Citi Standard",
    "RAIL_C": "Citi Tokenized",
}


# ─────────────────────────────────────────────────────────────
# Normalization helpers
# ─────────────────────────────────────────────────────────────

def _normalize_inverse(values: List[float]) -> List[float]:
    """Lower is better → invert to 0–100 score."""
    mn, mx = min(values), max(values)
    if mx == mn:
        return [100.0] * len(values)
    return [100.0 * (1 - (v - mn) / (mx - mn)) for v in values]


def _normalize_direct(values: List[float]) -> List[float]:
    """Higher is better → direct 0–100 score."""
    mn, mx = min(values), max(values)
    if mx == mn:
        return [100.0] * len(values)
    return [100.0 * (v - mn) / (mx - mn) for v in values]


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def optimize_route(
    fx_results: Dict[str, FxResult],
    liquidity_results: Dict[str, LiquidityCheckResult],
    priority: str = "NORMAL",
) -> RouteDecision:
    """
    Score all eligible rails and select the optimal one.

    Args:
        fx_results:        dict of rail_id → FxResult
        liquidity_results: dict of rail_id → LiquidityCheckResult
        priority:          NORMAL | URGENT | BULK

    Returns:
        RouteDecision with selected rail and full scoring matrix
    """
    weights = WEIGHT_PROFILES.get(priority.upper(), WEIGHT_PROFILES["NORMAL"])
    all_rail_ids = list(fx_results.keys())

    # ── Separate eligible vs ineligible ──────────────────────
    eligible_ids = [
        rid for rid in all_rail_ids
        if liquidity_results.get(rid, None) and liquidity_results[rid].eligible
    ]
    ineligible_ids = [rid for rid in all_rail_ids if rid not in eligible_ids]

    if not eligible_ids:
        raise ValueError(
            "No eligible rails available. All rails have insufficient liquidity "
            "or are inactive."
        )

    # ── Collect raw values for normalization ─────────────────
    costs     = [fx_results[r].total_cost_source  for r in eligible_ids]
    speeds    = [RAIL_SETTLEMENT_SEC.get(r, 60)   for r in eligible_ids]
    fx_rates  = [fx_results[r].effective_rate      for r in eligible_ids]
    risk_vals = [RAIL_RISK_SCORES.get(r, 0.5)      for r in eligible_ids]
    liq_vals  = [
        liquidity_results[r].available_amount / max(liquidity_results[r].required_amount, 1)
        for r in eligible_ids
    ]

    # ── Normalize ─────────────────────────────────────────────
    cost_scores      = _normalize_inverse(costs)    # lower cost → higher score
    speed_scores     = _normalize_inverse(speeds)   # faster → higher score
    fx_scores        = _normalize_direct(fx_rates)  # better rate → higher score
    risk_scores      = _normalize_direct(risk_vals) # safer rail → higher score
    liq_scores       = _normalize_direct(liq_vals)  # more headroom → higher score

    # ── Composite scores ──────────────────────────────────────
    rail_scores: List[RailScore] = []

    for i, rid in enumerate(eligible_ids):
        composite = (
            weights["cost"]      * cost_scores[i]  +
            weights["speed"]     * speed_scores[i] +
            weights["fx"]        * fx_scores[i]    +
            weights["risk"]      * risk_scores[i]  +
            weights["liquidity"] * liq_scores[i]
        )
        rail_scores.append(RailScore(
            rail_id=rid,
            rail_name=RAIL_NAMES.get(rid, rid),
            eligible=True,
            ineligible_reason=None,
            score=round(composite, 2),
            cost_score=round(cost_scores[i], 2),
            speed_score=round(speed_scores[i], 2),
            fx_score=round(fx_scores[i], 2),
            risk_score=round(risk_scores[i], 2),
            liquidity_score=round(liq_scores[i], 2),
            total_cost_source=fx_results[rid].total_cost_source,
            settlement_sec=RAIL_SETTLEMENT_SEC.get(rid, 60),
            effective_rate=fx_results[rid].effective_rate,
            net_recipient_amount=fx_results[rid].net_recipient_amount,
            weights_used=weights,
        ))

    # Add ineligible rails (score=0, eligible=False)
    for rid in ineligible_ids:
        liq = liquidity_results.get(rid)
        rail_scores.append(RailScore(
            rail_id=rid,
            rail_name=RAIL_NAMES.get(rid, rid),
            eligible=False,
            ineligible_reason=liq.reason if liq else "Rail inactive or unavailable",
            score=0.0,
            cost_score=0.0, speed_score=0.0, fx_score=0.0,
            risk_score=0.0, liquidity_score=0.0,
            total_cost_source=fx_results.get(rid, type('', (), {'total_cost_source': 0})()).total_cost_source if rid in fx_results else 0,
            settlement_sec=RAIL_SETTLEMENT_SEC.get(rid, 0),
            effective_rate=0.0,
            net_recipient_amount=0.0,
            weights_used=weights,
        ))

    # Sort: eligible first, then by score descending
    rail_scores.sort(key=lambda r: (not r.eligible, -r.score))

    # ── Select winner ─────────────────────────────────────────
    winner = next(r for r in rail_scores if r.eligible)

    # Build human-readable reason
    runner_up = next((r for r in rail_scores if r.eligible and r.rail_id != winner.rail_id), None)
    reason_parts = []
    if runner_up:
        cost_diff_pct = (
            (runner_up.total_cost_source - winner.total_cost_source)
            / max(runner_up.total_cost_source, 1) * 100
        )
        speed_diff = runner_up.settlement_sec - winner.settlement_sec
        if cost_diff_pct > 5:
            reason_parts.append(f"{cost_diff_pct:.0f}% lower total cost")
        if speed_diff > 0:
            reason_parts.append(f"{speed_diff}s faster settlement")
        if winner.fx_score > runner_up.fx_score:
            reason_parts.append("better effective FX rate")
    reason_parts.append("sufficient liquidity")
    reason_parts.append(f"priority: {priority}")
    reason = f"{winner.rail_name} selected — " + ", ".join(reason_parts)

    return RouteDecision(
        selected_rail_id=winner.rail_id,
        selected_rail_name=winner.rail_name,
        score=winner.score,
        settlement_sec=winner.settlement_sec,
        total_cost_source=winner.total_cost_source,
        effective_rate=winner.effective_rate,
        recipient_amount=winner.net_recipient_amount,
        reason=reason,
        all_rails=rail_scores,
        weights_used=weights,
    )
