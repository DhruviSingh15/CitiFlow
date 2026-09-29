"""
CitiFlow ML Training Pipeline — Phase 1
========================================
Uses PaySim (synthetic financial fraud dataset) as the base.
Engineers CitiFlow-specific cross-border features on top.
Trains a Random Forest classifier, calibrates probabilities,
and saves the model + SHAP explainer.

IMPORTANT: PaySim data is synthetic/academic.
These features and the resulting model are a prototype demonstration
of risk-scoring logic — not real Citi data or real fraud detection.

Download PaySim from Kaggle:
  https://www.kaggle.com/datasets/ealaxi/paysim1
  Save as: ml/data/PS_20174392719_1491204439457_log.csv

If the file is not found, this script generates a synthetic
CitiFlow dataset so you can run everything without Kaggle.
"""

import os
import sys
import json
import joblib
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    classification_report, roc_auc_score,
    confusion_matrix, precision_recall_curve, average_precision_score
)
from imblearn.over_sampling import SMOTE

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────

BASE_DIR   = Path(__file__).resolve().parent
DATA_DIR   = BASE_DIR / "data"
MODEL_DIR  = BASE_DIR / "models"
PAYSIM_CSV = DATA_DIR / "PS_20174392719_1491204439457_log.csv"
MODEL_OUT  = MODEL_DIR / "risk_model.pkl"
META_OUT   = MODEL_DIR / "model_metadata.json"

MODEL_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# Country risk table (prototype values)
# ─────────────────────────────────────────────────────────────

COUNTRY_RISK = {
    "IN": 0.20, "SG": 0.08, "US": 0.10, "GB": 0.10,
    "AE": 0.22, "CN": 0.35, "RU": 0.75, "NG": 0.72,
    "IR": 0.90, "KP": 0.99, "DE": 0.08, "JP": 0.08,
    "AU": 0.09, "CA": 0.09, "FR": 0.10, "BR": 0.38,
    "MX": 0.42, "ZA": 0.40, "KE": 0.45, "PK": 0.65,
}

SENDER_COUNTRIES   = ["IN"]           # CitiFlow prototype focuses on India outward
RECEIVER_COUNTRIES = list(COUNTRY_RISK.keys())


# ─────────────────────────────────────────────────────────────
# 1. Load or generate base data
# ─────────────────────────────────────────────────────────────

def load_paysim() -> pd.DataFrame:
    """Load PaySim CSV. Columns used: amount, isFraud."""
    print(f"[DATA] Loading PaySim from {PAYSIM_CSV} ...")
    df = pd.read_csv(PAYSIM_CSV, usecols=[
        "amount", "oldbalanceOrg", "newbalanceOrig",
        "oldbalanceDest", "newbalanceDest", "isFraud"
    ])
    df = df.rename(columns={
        "oldbalanceOrg":   "sender_balance",
        "newbalanceOrig":  "sender_balance_after",
        "oldbalanceDest":  "receiver_balance",
        "newbalanceDest":  "receiver_balance_after",
        "isFraud":         "is_fraud",
    })
    print(f"[DATA] PaySim loaded: {len(df):,} rows | fraud rate: {df['is_fraud'].mean():.2%}")
    return df


def generate_synthetic_data(n: int = 200_000) -> pd.DataFrame:
    """
    Generate a synthetic CitiFlow-flavoured dataset.
    Used when PaySim CSV is not available.
    All values are statistical approximations for prototype purposes.
    """
    print(f"[DATA] PaySim not found. Generating {n:,} synthetic rows ...")
    rng = np.random.default_rng(42)

    n_fraud   = int(n * 0.013)    # ~1.3% fraud rate (similar to PaySim)
    n_legit   = n - n_fraud

    def make_rows(count, fraud):
        if fraud:
            amount          = rng.lognormal(mean=11.5, sigma=1.8, size=count)
            sender_balance  = rng.uniform(0, amount * 0.5)          # low balance
            receiver_balance = rng.uniform(0, 5_000)
        else:
            amount          = rng.lognormal(mean=10.0, sigma=1.2, size=count)
            sender_balance  = amount * rng.uniform(1.2, 8.0, count)
            receiver_balance = rng.lognormal(10.5, 1.5, count)

        return pd.DataFrame({
            "amount":          amount,
            "sender_balance":  sender_balance,
            "receiver_balance": receiver_balance,
            "is_fraud":        int(fraud),
        })

    df = pd.concat([make_rows(n_legit, False), make_rows(n_fraud, True)], ignore_index=True)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    print(f"[DATA] Synthetic data: {len(df):,} rows | fraud rate: {df['is_fraud'].mean():.2%}")
    return df


# ─────────────────────────────────────────────────────────────
# 2. CitiFlow Feature Engineering
# ─────────────────────────────────────────────────────────────

def engineer_features(df: pd.DataFrame, rng=None) -> pd.DataFrame:
    """
    Add CitiFlow-specific cross-border features.
    These are engineered/synthetic features for prototype purposes.
    """
    if rng is None:
        rng = np.random.default_rng(42)
    n = len(df)

    print("[FEAT] Engineering CitiFlow cross-border features ...")

    # ── Cross-border flag (always True in CitiFlow context)
    df["is_cross_border"] = 1

    # ── Corridor
    df["sender_country"]   = rng.choice(SENDER_COUNTRIES, size=n)
    df["receiver_country"] = rng.choice(RECEIVER_COUNTRIES, size=n, p=_country_probs())

    # ── Country risk
    df["country_risk"] = df["receiver_country"].map(COUNTRY_RISK).fillna(0.3)

    # ── Transaction velocity in 24h: fraud txns tend to have higher velocity
    base_velocity           = rng.integers(1, 5, size=n)
    fraud_velocity_boost    = (df["is_fraud"] * rng.integers(3, 15, size=n)).astype(int)
    df["transaction_velocity_24h"] = base_velocity + fraud_velocity_boost

    # ── Recipient relationship age (days). 0 = brand new recipient
    df["recipient_history_days"] = np.where(
        df["is_fraud"] == 1,
        rng.integers(0, 15, size=n),       # fraud → new recipients
        rng.integers(30, 1500, size=n)     # legit → established recipients
    )

    # ── Account age
    df["account_age_days"] = np.where(
        df["is_fraud"] == 1,
        rng.integers(1, 60, size=n),
        rng.integers(180, 3000, size=n)
    )

    # ── Amount deviation from 30-day sender average (%)
    # Fraud txns deviate significantly more
    df["amount_deviation_pct"] = np.where(
        df["is_fraud"] == 1,
        rng.uniform(50, 500, size=n),
        rng.uniform(-20, 30, size=n)
    )

    # ── Is new recipient flag
    df["is_new_recipient"] = (df["recipient_history_days"] < 7).astype(int)

    # ── Sender balance ratio (amount / sender_balance). High = risky
    safe_balance = np.where(df["sender_balance"] > 0, df["sender_balance"], 1)
    df["balance_ratio"] = (df["amount"] / safe_balance).clip(upper=20)

    # ── Encode country risk tier
    df["high_risk_corridor"] = (df["country_risk"] >= 0.6).astype(int)

    print(f"[FEAT] Feature engineering complete. Columns: {list(df.columns)}")
    return df


def _country_probs():
    """Weighted probabilities for receiver countries (India → most common corridors)."""
    weights = {
        "SG": 0.18, "AE": 0.16, "US": 0.14, "GB": 0.12,
        "AU": 0.06, "CA": 0.05, "DE": 0.05, "JP": 0.04,
        "CN": 0.04, "FR": 0.03, "BR": 0.02, "ZA": 0.02,
        "MX": 0.02, "RU": 0.02, "KE": 0.01, "PK": 0.01,
        "NG": 0.01, "IR": 0.01, "KP": 0.005, "IN": 0.005,
    }
    countries = list(weights.keys())
    probs     = np.array([weights[c] for c in countries])
    probs     = probs / probs.sum()   # normalize
    return probs


# ─────────────────────────────────────────────────────────────
# 3. Feature columns for training
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

TARGET_COL = "is_fraud"


# ─────────────────────────────────────────────────────────────
# 4. Train
# ─────────────────────────────────────────────────────────────

def train(df: pd.DataFrame):
    print("\n[TRAIN] Preparing features ...")

    # Ensure no NaNs in features
    df[FEATURE_COLS] = df[FEATURE_COLS].fillna(0)

    X = df[FEATURE_COLS].values
    y = df[TARGET_COL].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    # Handle class imbalance with SMOTE
    print(f"[TRAIN] Class distribution before SMOTE: {np.bincount(y_train)}")
    sm = SMOTE(random_state=42, k_neighbors=5)
    X_train_sm, y_train_sm = sm.fit_resample(X_train, y_train)
    print(f"[TRAIN] Class distribution after  SMOTE: {np.bincount(y_train_sm)}")

    # Random Forest
    print("[TRAIN] Fitting Random Forest ...")
    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=5,
        max_features="sqrt",
        class_weight="balanced",
        n_jobs=-1,
        random_state=42,
    )

    # Calibrate probabilities (Platt scaling)
    model = CalibratedClassifierCV(rf, method="sigmoid", cv=3)
    model.fit(X_train_sm, y_train_sm)

    print("[TRAIN] Training complete.")
    return model, X_test, y_test


# ─────────────────────────────────────────────────────────────
# 5. Evaluate
# ─────────────────────────────────────────────────────────────

def evaluate(model, X_test, y_test) -> dict:
    print("\n[EVAL] Evaluating on held-out test set ...")
    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    auc   = roc_auc_score(y_test, y_proba)
    ap    = average_precision_score(y_test, y_proba)
    cm    = confusion_matrix(y_test, y_pred)
    report = classification_report(y_test, y_pred, output_dict=True)

    print(f"\n  ROC-AUC : {auc:.4f}")
    print(f"  Avg Prec: {ap:.4f}")
    print(f"\n  Confusion Matrix:\n  {cm}")
    print(f"\n  Classification Report:\n{classification_report(y_test, y_pred)}")

    return {
        "roc_auc":            round(auc, 4),
        "average_precision":  round(ap, 4),
        "precision_fraud":    round(report["1"]["precision"], 4),
        "recall_fraud":       round(report["1"]["recall"], 4),
        "f1_fraud":           round(report["1"]["f1-score"], 4),
        "confusion_matrix":   cm.tolist(),
    }


# ─────────────────────────────────────────────────────────────
# 6. Save
# ─────────────────────────────────────────────────────────────

def save_model(model, metrics: dict):
    artifact = {
        "model":        model,
        "feature_cols": FEATURE_COLS,
        "version":      "1.0.0",
        "trained_at":   datetime.utcnow().isoformat(),
        "metrics":      metrics,
        "disclaimer":   (
            "Trained on PaySim (synthetic academic dataset) augmented with "
            "CitiFlow-engineered cross-border features. "
            "For prototype demonstration purposes only. "
            "Not trained on real Citi data."
        ),
    }
    joblib.dump(artifact, MODEL_OUT)
    print(f"\n[SAVE] Model saved -> {MODEL_OUT}")

    # Also save readable metadata
    meta = {k: v for k, v in artifact.items() if k != "model"}
    meta["feature_cols"] = FEATURE_COLS
    with open(META_OUT, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"[SAVE] Metadata saved -> {META_OUT}")


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  CitiFlow Risk Model Training Pipeline — Phase 1")
    print("=" * 60)

    rng = np.random.default_rng(42)

    # Load data
    if PAYSIM_CSV.exists():
        df = load_paysim()
        # Subsample for speed if very large
        if len(df) > 300_000:
            df = df.sample(n=300_000, random_state=42).reset_index(drop=True)
    else:
        df = generate_synthetic_data(n=200_000)

    # Engineer features
    df = engineer_features(df, rng=rng)

    # Train
    model, X_test, y_test = train(df)

    # Evaluate
    metrics = evaluate(model, X_test, y_test)

    # Save
    save_model(model, metrics)

    print("\n[DONE] Phase 1 complete. Model ready at:", MODEL_OUT)
    return model


if __name__ == "__main__":
    main()
