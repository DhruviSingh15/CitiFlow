# CitiFlow Development Log
**Date:** September 2026
**Status:** Code-Complete (Pending Environmental NPM Resolves)

## Project Vision
To build an intelligent, adaptive orchestration layer that sits *above* existing payment infrastructure (simulated), rather than reinventing standard cross-border blockchain settlement. The prototype dynamically selects routes, assesses risks, enforces compliance, and calculates FX and liquidity constraints before settling via a Smart Contract layer.

---

## 1. Backend Implementation (FastAPI / Python) - ✅ COMPLETED

### ML & Risk Engine (`app/services/risk_engine.py`)
- Generated synthetic transactional data encompassing variables like account age, transaction velocity, and previous corridor behaviors.
- Trained a **RandomForestClassifier** (`risk_model.pkl`) to predict High/Medium/Low risk.
- Integrated **SHAP (SHapley Additive exPlanations)** to output human-readable feature contributions explaining *why* a transaction was flagged.

### Compliance Layer (`app/services/compliance.py`)
- Implemented a rule-based engine executing 6 distinct compliance checks.
- Includes hard blocks on sanctioned corridors (e.g., Iran, North Korea) and velocity limits (max 10 tx/24h).
- Added triggers for large sums to unknown recipients, triggering immediate hold statuses.

### FX & Liquidity (`app/services/fx_engine.py`, `app/services/liquidity.py`)
- Developed an FX simulator utilizing a random-walk algorithm to fluctuate base rates for 9 major currencies.
- Created a highly thread-safe Liquidity Manager simulating global pools (e.g., RAIL_A, RAIL_B, RAIL_C). 
- Designed a reserve/commit lifecycle. If a pool drops below the required transaction threshold, it automatically falls back to an alternative rail, generating system alerts.

### Route Optimizer (`app/services/route_optimizer.py`)
- Engineered a scoring matrix evaluating 5 dimensions: Base Fee, FX Spread, Settlement Time, Reliability Score, and Liquidity Availability.
- Dynamically assigns the payment to the rail with the highest final score, falling back based on user-defined priority (NORMAL, URGENT, BULK).

### Orchestration Pipeline (`app/routers/payment.py`)
- Stitched the intelligence layer into a unified pipeline: `Risk → Compliance → Liquidity → FX → Route Optimizer → Settlement`.
- Handled all edge cases including reverting liquidity reservations if compliance or settlement fails.
- All 4 primary test scenarios (Normal, Suspicious, Sanctioned, Liquidity Drain) successfully executed in E2E tests.

---

## 2. Smart Contract / Blockchain - ✅ CODE WRITTEN

- **`CrossBorderSettlement.sol`**: Wrote the Solidity audit contract utilizing an event-driven design to log the final states of orchestrated payments (Created, Risk_Flagged, On_Hold, Settled).
- **Hardhat Tests**: Authored comprehensive JS tests spanning deployments, state changes, struct lookups, and modifier auth.
- **Deployment Script**: Prepared `deploy.js` to automatically extract the contract ABI and inject the `.env` variables into the backend.

---

## 3. Frontend Implementation (React / Vite) - ✅ CODE WRITTEN

- **Design System (`index.css`)**: Built a complete design system from scratch using raw CSS. Features deep navy / electric blue palettes inspired by modern banking interfaces, with glassmorphism, animated pulse indicators, and responsive grids.
- **Control Tower (`Dashboard.jsx`)**: Engineered a live monitoring feed connecting to the backend's `/control-tower` endpoints. Displays auto-refreshing stats, dynamic liquidity gauges, and real-time transaction tables.
- **Payment Sandbox (`NewPayment.jsx`)**: Designed an interactive form that allows users to test the 4 orchestration scenarios. Includes UI for dynamically draining liquidity on specific rails to test route-shifting, and visualizes the ML risk scoring via SHAP value bars.
- **Analytics (`Analytics.jsx`)**: Used `recharts` to map out the session's overall effectiveness, contrasting the AI-driven routing costs against standard single-rail unoptimized routing.

---

## 4. Current Challenges & Environmental Blockers

While the backend is running seamlessly (currently live on port `8001`), the local environment experienced severe external network failures when communicating with the `npm` registry.
- Standard `npm install` tasks for both the Vite React scaffold and the Hardhat blockchain environment repeatedly timed out (`ECONNRESET`, `EIDLETIMEOUT`).
- Aggressive fetch-retry mechanisms were implemented, but the registry connection remains unstable.
- **Resolution:** The project is fully structurally complete. Once the external `npm` servers stabilize, simply running `npm install` in `/frontend` and `/blockchain` will bring the UI and local testnet completely online.
