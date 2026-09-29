"""
evaluate.py — standalone model evaluation script
Run after train.py to re-evaluate a saved model on new data.

Usage:
    cd backend
    python ml/evaluate.py
"""

import joblib
import json
import numpy as np
from pathlib import Path
from sklearn.metrics import (
    classification_report, roc_auc_score,
    confusion_matrix, average_precision_score,
    roc_curve, precision_recall_curve
)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_DIR  = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"
MODEL_OUT = MODEL_DIR / "risk_model.pkl"


def load_artifact():
    if not MODEL_OUT.exists():
        raise FileNotFoundError(f"Model not found at {MODEL_OUT}. Run train.py first.")
    return joblib.load(MODEL_OUT)


def plot_roc(y_test, y_proba, out_path):
    fpr, tpr, _ = roc_curve(y_test, y_proba)
    auc = roc_auc_score(y_test, y_proba)
    plt.figure(figsize=(7, 5))
    plt.plot(fpr, tpr, lw=2, label=f"ROC (AUC = {auc:.3f})")
    plt.plot([0,1], [0,1], "--", color="gray")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("CitiFlow Risk Model — ROC Curve")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path)
    print(f"[EVAL] ROC curve saved → {out_path}")


def plot_pr(y_test, y_proba, out_path):
    prec, rec, _ = precision_recall_curve(y_test, y_proba)
    ap = average_precision_score(y_test, y_proba)
    plt.figure(figsize=(7, 5))
    plt.plot(rec, prec, lw=2, label=f"PR (AP = {ap:.3f})")
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title("CitiFlow Risk Model — Precision-Recall Curve")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path)
    print(f"[EVAL] PR curve saved → {out_path}")


def run_demo_predictions(model, feature_cols):
    """Run the 4 demo scenarios from the Phase 0 spec."""
    print("\n[DEMO] Running Phase 11 test scenarios ...")
    scenarios = [
        {
            "name": "Scenario A — Normal Payment (₹1L IN→SG)",
            "features": [100_000, 500_000, 2, 180, 730, 5.0, 0.08, 0, 0.2, 0],
        },
        {
            "name": "Scenario B — Suspicious (₹25L, high velocity, new recipient)",
            "features": [2_500_000, 100_000, 18, 0, 30, 320.0, 0.08, 1, 25.0, 0],
        },
        {
            "name": "Scenario C — Liquidity Failure Trigger (₹1L IN→RU)",
            "features": [100_000, 400_000, 3, 90, 500, 10.0, 0.75, 0, 0.25, 1],
        },
        {
            "name": "Scenario D — Dynamic Route Change (₹5L IN→AE)",
            "features": [500_000, 800_000, 4, 200, 900, 12.0, 0.22, 0, 0.625, 0],
        },
    ]

    for s in scenarios:
        X = np.array([s["features"]])
        prob = model.predict_proba(X)[0][1]
        score = min(int(round(prob * 100)), 100)
        level = "LOW" if score <= 40 else "MEDIUM" if score <= 70 else "HIGH"
        decision = "APPROVE" if score <= 70 else "REVIEW" if score <= 85 else "BLOCK"
        print(f"\n  {s['name']}")
        print(f"    Risk Score : {score}/100")
        print(f"    Risk Level : {level}")
        print(f"    Decision   : {decision}")

    print()


def main():
    print("=" * 60)
    print("  CitiFlow Risk Model — Evaluation")
    print("=" * 60)

    artifact    = load_artifact()
    model       = artifact["model"]
    feature_cols = artifact["feature_cols"]
    metrics     = artifact.get("metrics", {})

    print(f"\n  Model version : {artifact.get('version')}")
    print(f"  Trained at    : {artifact.get('trained_at')}")
    print(f"\n  Stored metrics:")
    for k, v in metrics.items():
        if k != "confusion_matrix":
            print(f"    {k}: {v}")

    run_demo_predictions(model, feature_cols)
    print("✓ Evaluation complete.")


if __name__ == "__main__":
    main()
