"""
Risk Router — POST /api/v1/risk/analyze
GET  /api/v1/risk/health
"""
from fastapi import APIRouter, HTTPException, Depends
from app.schemas.risk import RiskAnalyzeRequest, RiskAnalyzeResponse, ShapFactor, ShapExplanation
from app.services import risk_engine

router = APIRouter(prefix="/risk", tags=["Risk Engine"])


@router.post("/analyze", response_model=RiskAnalyzeResponse, summary="Analyze transaction risk")
async def analyze_risk(request: RiskAnalyzeRequest):
    """
    Run the CitiFlow risk model on the given transaction features.

    Returns a risk_score (0–100), risk_level (LOW/MEDIUM/HIGH),
    decision (APPROVE/REVIEW/BLOCK), and SHAP-based explanation.
    """
    try:
        result = risk_engine.analyze_risk(request.model_dump())
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Risk model not loaded. Run `python ml/train.py` first. Error: {e}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Risk analysis failed: {e}")

    # Build response
    shap_data = result["shap_explanation"]
    factors   = [
        ShapFactor(
            feature=f["feature"],
            contribution=f["contribution"],
            direction=f["direction"],
            display_value=f["display_value"],
        )
        for f in shap_data["top_factors"]
    ]

    return RiskAnalyzeResponse(
        risk_score=result["risk_score"],
        risk_level=result["risk_level"],
        decision=result["decision"],
        shap_explanation=ShapExplanation(
            top_factors=factors,
            base_value=shap_data["base_value"],
            summary=shap_data["summary"],
        ),
        model_version=result["model_version"],
        assessed_at=result["assessed_at"],
    )


@router.get("/health", summary="Risk model health check")
async def risk_health():
    """Returns model version, training date and evaluation metrics."""
    return risk_engine.health_check()
