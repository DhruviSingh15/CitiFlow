"""
Payment Router — Phase 5 (Integration)
========================================
POST /api/v1/payment/process  — full CitiFlow orchestration pipeline
GET  /api/v1/payment/{ref}    — retrieve a transaction by reference
"""

import time
import uuid
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.schemas.payment import (
    PaymentRequest, PaymentResponse,
    RiskSummary, ComplianceSummary,
    SelectedRoute, RouteScore, BlockchainProof,
    SettlementSummary, TransactionStatus,
)
from app.services import risk_engine
from app.services.compliance import run_compliance
from app.services.fx_engine import calculate_fx, compare_rails
from app.services.liquidity import check_all_rails, reserve_liquidity, release_liquidity
from app.services.route_optimizer import optimize_route
from app.services import settlement as settlement_svc

router = APIRouter(prefix="/payment", tags=["Payment Orchestration"])

# ── In-memory transaction store for demo (replace with DB in production) ──
_transactions: dict = {}


def _make_ref() -> str:
    """Generate a short, readable transaction reference."""
    return f"TXN{uuid.uuid4().hex[:6].upper()}"


# ─────────────────────────────────────────────────────────────
# POST /payment/process
# ─────────────────────────────────────────────────────────────

@router.post("/process", response_model=PaymentResponse, summary="Process a cross-border payment")
async def process_payment(request: PaymentRequest, background_tasks: BackgroundTasks):
    """
    Full CitiFlow orchestration pipeline:
    Risk → Compliance → Liquidity → FX → Route Optimization → Settlement → Blockchain
    """
    start_ms  = int(time.time() * 1000)
    tx_ref    = _make_ref()
    all_rails = ["RAIL_A", "RAIL_B", "RAIL_C"]

    # ── STEP 1: Risk Analysis ──────────────────────────────────
    risk_input = {
        "amount":                   request.amount,
        "transaction_velocity_24h": request.transaction_velocity_24h,
        "account_age_days":         request.account_age_days,
        "recipient_history_days":   request.recipient_history_days,
        "country_risk_score":       0.2,   # default; will be overridden by engine
        "sender_country":           request.sender_country,
        "receiver_country":         request.receiver_country,
        "amount_deviation_pct":     0.0,
    }

    try:
        risk_result = risk_engine.analyze_risk(risk_input)
    except FileNotFoundError:
        raise HTTPException(503, "Risk model not loaded. Run `python ml/train.py` first.")

    risk_summary = RiskSummary(
        score=risk_result["risk_score"],
        level=risk_result["risk_level"],
        decision=risk_result["decision"],
        top_factors=[
            {
                "feature":      f["feature"],
                "label":        f.get("label", f["feature"]),
                "contribution": f["contribution"],
                "direction":    f["direction"],
            }
            for f in risk_result["shap_explanation"]["top_factors"]
        ],
    )

    # ── STEP 2: Compliance ────────────────────────────────────
    compliance_input = {
        **risk_input,
        "risk_score":               risk_result["risk_score"],
        "transaction_velocity_24h": request.transaction_velocity_24h,
    }
    compliance_result = run_compliance(compliance_input)

    compliance_summary = ComplianceSummary(
        passed=compliance_result.passed,
        rules_triggered=compliance_result.rules_triggered,
        notes=compliance_result.notes,
    )

    # ── If BLOCKED or REVIEW → return early, no settlement ────
    if compliance_result.final_decision in ("BLOCK", "REVIEW"):
        status = (
            TransactionStatus.FAILED   if compliance_result.final_decision == "BLOCK"
            else TransactionStatus.ON_HOLD
        )
        elapsed = int(time.time() * 1000) - start_ms

        record = {
            "ref": tx_ref, "status": status,
            "risk": risk_summary, "compliance": compliance_summary,
            "amount": request.amount,
            "source_currency": request.source_currency,
            "target_currency": request.target_currency,
            "corridor": f"{request.sender_country} -> {request.receiver_country}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if not request.dry_run:
            _transactions[tx_ref] = record

        return PaymentResponse(
            transaction_ref=tx_ref,
            status=status,
            risk=risk_summary,
            compliance=compliance_summary,
            selected_route=None,
            all_routes_evaluated=[],
            settlement=None,
            processing_time_ms=elapsed,
        )

    # ── STEP 3: Liquidity Check ───────────────────────────────
    liquidity_results = check_all_rails(request.amount)

    # ── STEP 4: FX Calculation (all rails) ───────────────────
    fx_results = {}
    for rail_id in all_rails:
        try:
            fx_results[rail_id] = calculate_fx(
                request.amount,
                request.source_currency,
                request.target_currency,
                rail_id,
            )
        except ValueError:
            pass   # skip unsupported currency pairs for this rail

    if not fx_results:
        raise HTTPException(422, f"FX rate not available for {request.source_currency}→{request.target_currency}")

    # ── STEP 5: Route Optimization ────────────────────────────
    try:
        route_decision = optimize_route(
            fx_results=fx_results,
            liquidity_results=liquidity_results,
            priority=request.priority.value,
        )
    except ValueError as e:
        raise HTTPException(422, f"Route optimization failed: {e}")

    # Build route response objects
    selected_route = SelectedRoute(
        rail_id=route_decision.selected_rail_id,
        rail_name=route_decision.selected_rail_name,
        score=route_decision.score,
        settlement_sec=route_decision.settlement_sec,
        total_cost_source=route_decision.total_cost_source,
        effective_rate=route_decision.effective_rate,
        recipient_amount=route_decision.recipient_amount,
        reason=route_decision.reason,
    )

    all_routes_evaluated = [
        RouteScore(
            rail_id=r.rail_id,
            rail_name=r.rail_name,
            score=r.score,
            eligible=r.eligible,
            ineligible_reason=r.ineligible_reason,
        )
        for r in route_decision.all_rails
    ]

    # ── STEP 6: Reserve Liquidity ─────────────────────────────
    if not request.dry_run:
        reserve_liquidity(route_decision.selected_rail_id, request.amount)

    # ── STEP 7: Settlement ────────────────────────────────────
    settlement_summary = None
    final_status = TransactionStatus.SETTLEMENT_PENDING

    if not request.dry_run:
        try:
            result = await settlement_svc.settle(
                transaction_ref=tx_ref,
                sender_id=request.sender_id,
                receiver_id=request.receiver_id,
                amount=route_decision.recipient_amount,
                currency=request.target_currency,
                rail_id=route_decision.selected_rail_id,
                settlement_sec=route_decision.settlement_sec,
            )

            final_status = TransactionStatus.SETTLED if result.success else TransactionStatus.FAILED

            # Release reservation after settlement
            background_tasks.add_task(
                release_liquidity,
                route_decision.selected_rail_id,
                request.amount,
            )

            blockchain_proof = None
            if result.blockchain_tx_hash:
                blockchain_proof = BlockchainProof(
                    network="hardhat-local",
                    contract=str((lambda s: s.contract_address)(
                        __import__("app.config", fromlist=["get_settings"]).get_settings()
                    )),
                    tx_hash=result.blockchain_tx_hash,
                    block_number=None,
                    record_id=result.contract_record_id,
                )

            settlement_summary = SettlementSummary(
                settled_at=result.settled_at,
                settlement_time_ms=result.settlement_time_ms,
                blockchain=blockchain_proof,
            )

        except Exception as e:
            final_status = TransactionStatus.FAILED
            release_liquidity(route_decision.selected_rail_id, request.amount)
    else:
        final_status = TransactionStatus.ROUTE_SELECTED   # dry_run stops here

    elapsed = int(time.time() * 1000) - start_ms

    # ── Store record in memory ─────────────────────────────────
    record = {
        "ref":             tx_ref,
        "status":          final_status,
        "risk":            risk_summary,
        "compliance":      compliance_summary,
        "selected_route":  selected_route,
        "amount":          request.amount,
        "source_currency": request.source_currency,
        "target_currency": request.target_currency,
        "corridor":        f"{request.sender_country} -> {request.receiver_country}",
        "created_at":      datetime.now(timezone.utc).isoformat(),
        "settled_at":      settlement_summary.settled_at if settlement_summary else None,
    }
    _transactions[tx_ref] = record

    return PaymentResponse(
        transaction_ref=tx_ref,
        status=final_status,
        risk=risk_summary,
        compliance=compliance_summary,
        selected_route=selected_route,
        all_routes_evaluated=all_routes_evaluated,
        settlement=settlement_summary,
        processing_time_ms=elapsed,
    )


# ─────────────────────────────────────────────────────────────
# GET /payment/{ref}
# ─────────────────────────────────────────────────────────────

@router.get("/{ref}", summary="Get transaction by reference")
async def get_transaction(ref: str):
    """Retrieve a processed transaction by its reference (e.g. TXN1A2B3C)."""
    record = _transactions.get(ref.upper())
    if not record:
        raise HTTPException(404, f"Transaction {ref} not found")
    return record


def get_all_transactions() -> dict:
    """Expose transaction store to Control Tower router."""
    return _transactions
