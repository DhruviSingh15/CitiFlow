"""
CitiFlow FastAPI Application — Entry Point
==========================================
Phases 1-6: All services integrated.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import time

from app.config import get_settings
from app.routers import risk as risk_router
from app.routers import payment as payment_router
from app.routers import fx_routes as fx_router
from app.routers import control_tower as ct_router

settings = get_settings()

# ─────────────────────────────────────────────────────────────
# App Init
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="CitiFlow API",
    description=(
        "Intelligent Payment Orchestration & Settlement Optimization. "
        "CitiFlow is a prototype AI-driven orchestration layer for cross-border payments. "
        "All payment rails and market data are simulated."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = str(round((time.time() - start) * 1000, 2))
    return response


# ─────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────

API_PREFIX = "/api/v1"

app.include_router(risk_router.router,    prefix=API_PREFIX)
app.include_router(payment_router.router, prefix=API_PREFIX)
app.include_router(fx_router.router,      prefix=API_PREFIX)
app.include_router(ct_router.router,      prefix=API_PREFIX)


# ─────────────────────────────────────────────────────────────
# Root & Health
# ─────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {
        "service":   "CitiFlow API",
        "version":   "1.0.0",
        "status":    "running",
        "endpoints": {
            "docs":             "/docs",
            "risk":             f"{API_PREFIX}/risk/analyze",
            "payment":          f"{API_PREFIX}/payment/process",
            "fx":               f"{API_PREFIX}/fx/calculate",
            "routes":           f"{API_PREFIX}/routes/available",
            "control_tower":    f"{API_PREFIX}/control-tower/stats",
            "liquidity":        f"{API_PREFIX}/control-tower/liquidity",
        },
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, reload=True)
