"""
Risk Engine Service — CitiFlow Phase 1
=======================================
Loads the trained Random Forest model and SHAP explainer.
Converts calibrated fraud probability → risk_score (0–100).
Returns risk_level, decision, and SHAP-based explanation.

Risk Score thresholds:
  0–40   LOW     → APPROVE
  41–70  MEDIUM  → APPROVE (with enhanced monitoring flag)
  71–85  HIGH    → REVIEW
  86–100 HIGH    → BLOCK
"""

import os
import joblib
import shap
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from functools import lru_cache
from typing import Dict, Any

from app.config import get_settings

# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────

FEATURE_COLS = [
    "amount",
    "sender_balance",
    "transaction_velocity_24h",
    "recipient_history_days",
    "account_age_days",
    "amount_deviation_pct",
    "country_risk",
    "is_new_recipient",
    "balance_ratio",
    "high_risk_corridor",
]

FEATURE_DISPLAY = {
    "amount":                   "Transaction Amount",
    "sender_balance":           "Sender Account Balance",
    "transaction_velocity_24h": "Transaction Velocity (24h)",
    "recipient_history_days":   "Recipient Relationship Age",
    "account_age_days":         "Account Age",
    "amount_deviation_pct":     "Amount Deviation from Avg",
    "country_risk":             "Destination Country Risk",
    "is_new_recipient":         "New Recipient Flag",
    "balance_ratio":            "Amount-to-Balance Ratio",
    "high_risk_corridor":       "High-Risk Corridor",
}

COUNTRY_RISK = {
    "IN": 0.20, "SG": 0.08, "US": 0.10, "GB": 0.10,
    "AE": 0.22, "CN": 0.35, "RU": 0.75, "NG": 0.72,
    "IR": 0.90, "KP": 0.99, "DE": 0.08, "JP": 0.08,
    "AU": 0.09, "CA": 0.09, "FR": 0.10, "BR": 0.38,
    "MX": 0.42, "ZA": 0.40, "KE": 0.45, "PK": 0.65,
}


# ─────────────────────────────────────────────────────────────
# Model Loading
# ─────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_artifact() -> Dict[str, Any]:
    """Load model artifact once and cache in memory."""
    settings = get_settings()
    model_path = Path(settings.risk_model_path)

    if not model_path.exists():
        raise FileNotFoundError(
            f"Risk model not found at {model_path}. "
            "Run `python ml/train.py` first."
        )

    artifact = joblib.load(model_path)
    print(f"[RiskEngine] Loaded model v{artifact.get('version','?')} "
          f"trained at {artifact.get('trained_at','?')}")
    return artifact


def _get_model():
    return _load_artifact()["model"]


def _get_shap_explainer():
    """Build SHAP KernelExplainer using a small background dataset."""
    model = _get_model()
    # Build a small representative background (100 zero-baseline rows)
    background = np.zeros((100, len(FEATURE_COLS)))
    explainer = shap.KernelExplainer(
        lambda x: model.predict_proba(x)[:, 1],
        background,
        silent=True
    )
    return explainer


# ─────────────────────────────────────────────────────────────
# Feature Preparation
# ─────────────────────────────────────────────────────────────

def _build_feature_vector(request_data: Dict[str, Any]) -> np.ndarray:
    """
    Convert API request into model feature vector.
    Derives synthetic features not directly in the request.
    """
    amount          = float(request_data.get("amount", 0))
    sender_balance  = float(request_data.get("sender_balance") or amount * 3.0)
    velocity        = int(request_data.get("transaction_velocity_24h", 1))
    recipient_hist  = int(request_data.get("recipient_history_days", 90))
    account_age     = int(request_data.get("account_age_days", 365))
    amt_deviation   = float(request_data.get("amount_deviation_pct", 0.0))
    receiver_country = request_data.get("receiver_country", "SG")

    country_risk    = COUNTRY_RISK.get(receiver_country.upper(), 0.3)
    is_new_recip    = 1 if recipient_hist < 7 else 0
    balance_ratio   = min(amount / max(sender_balance, 1), 20.0)
    high_risk       = 1 if country_risk >= 0.6 else 0

    vector = np.array([[
        amount,
        sender_balance,
        velocity,
        recipient_hist,
        account_age,
        amt_deviation,
        country_risk,
        is_new_recip,
        balance_ratio,
        high_risk,
    ]], dtype=float)

    return vector


# ─────────────────────────────────────────────────────────────
# Score → Level / Decision
# ─────────────────────────────────────────────────────────────

def _score_to_level_decision(score: int):
    if score <= 40:
        return "LOW", "APPROVE"
    elif score <= 70:
        return "MEDIUM", "APPROVE"
    elif score <= 85:
        return "HIGH", "REVIEW"
    else:
        return "HIGH", "BLOCK"


# ─────────────────────────────────────────────────────────────
# SHAP Explanation
# ─────────────────────────────────────────────────────────────

def _build_shap_explanation(feature_vector: np.ndarray, base_prob: float) -> Dict[str, Any]:
    """
    Compute SHAP values and return top-5 contributors.
    Falls back to feature importance if SHAP fails.
    """
    try:
        explainer = _get_shap_explainer()
        shap_vals = explainer.shap_values(feature_vector, nsamples=50, silent=True)
        vals      = shap_vals[0] if isinstance(shap_vals, list) else shap_vals.flatten()
    except Exception:
        # Fallback: use model feature importances as proxy
        model = _get_model()
        try:
            # CalibratedClassifierCV wraps the base estimator
            base_rf = model.calibrated_classifiers_[0].estimator
            vals    = base_rf.feature_importances_ * base_prob
        except Exception:
            vals = np.zeros(len(FEATURE_COLS))

    # Pair with feature names and sort by absolute contribution
    pairs = sorted(
        zip(FEATURE_COLS, vals),
        key=lambda x: abs(x[1]),
        reverse=True
    )

    factors = []
    for feat, contrib in pairs[:5]:
        factors.append({
            "feature":      feat,
            "label":        FEATURE_DISPLAY.get(feat, feat),
            "contribution": round(float(contrib), 4),
            "direction":    "risk_increasing" if contrib > 0 else "risk_reducing",
            "display_value": _format_contribution(feat, contrib, feature_vector),
        })

    # Human-readable summary
    top_driver = factors[0]["label"] if factors else "multiple factors"
    direction  = factors[0]["direction"] if factors else "risk_increasing"
    summary = (
        f"Primary driver: {top_driver} "
        f"({'increases' if direction == 'risk_increasing' else 'reduces'} risk). "
        f"Top {min(len(factors), 5)} factors shown."
    )

    return {
        "top_factors": factors,
        "base_value":  round(float(base_prob), 4),
        "summary":     summary,
    }


def _format_contribution(feature: str, contrib: float, vec: np.ndarray) -> str:
    pct = abs(round(contrib * 100, 1))
    return f"+{pct}% risk" if contrib > 0 else f"-{pct}% risk"


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def analyze_risk(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for risk analysis.

    Args:
        request_data: dict matching RiskAnalyzeRequest fields

    Returns:
        dict with risk_score, risk_level, decision, shap_explanation, assessed_at
    """
    model  = _get_model()
    vector = _build_feature_vector(request_data)

    # Raw fraud probability from calibrated model
    fraud_prob = float(model.predict_proba(vector)[0][1])

    # Convert to 0–100 risk score
    risk_score = min(int(round(fraud_prob * 100)), 100)

    # Determine level and decision
    risk_level, decision = _score_to_level_decision(risk_score)

    # SHAP explanation
    shap_explanation = _build_shap_explanation(vector, fraud_prob)

    return {
        "risk_score":       risk_score,
        "risk_level":       risk_level,
        "decision":         decision,
        "shap_explanation": shap_explanation,
        "model_version":    _load_artifact().get("version", "1.0.0"),
        "assessed_at":      datetime.now(timezone.utc).isoformat(),
    }


def health_check() -> Dict[str, Any]:
    """Returns model metadata for the /health endpoint."""
    try:
        artifact = _load_artifact()
        return {
            "status":      "ok",
            "version":     artifact.get("version"),
            "trained_at":  artifact.get("trained_at"),
            "metrics":     artifact.get("metrics"),
        }
    except FileNotFoundError as e:
        return {"status": "model_not_found", "error": str(e)}
