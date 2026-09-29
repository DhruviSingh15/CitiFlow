# CitiFlow

**Intelligent Payment Orchestration & Settlement Optimization**

> CitiFlow is a prototype AI-driven orchestration layer for cross-border payments.
> All payment rails and market data are simulated.

---

## Architecture

```
React + Vite Dashboard
       ↓
FastAPI Backend (port 8001)
  ├── Risk Engine   (Random Forest + SHAP)
  ├── Compliance    (Rule engine)
  ├── FX Engine     (Simulated live rates)
  ├── Liquidity     (Thread-safe pool manager)
  ├── Route Optimizer (Weighted scoring)
  └── Settlement    → Hardhat local blockchain
```

---

## Quick Start

### 1. Backend (Python 3.11)

```bash
cd backend
pip install -r requirements.txt

# Train the risk model (first time only)
python ml/train.py

# Start the API
python -m uvicorn app.main:app --port 8001
# → http://localhost:8001/docs
```

### 2. Frontend (Node 18+)

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### 3. Blockchain (Hardhat)

```bash
cd blockchain
npm install

# Terminal A: Start local Hardhat node
npx hardhat node

# Terminal B: Deploy contract
npx hardhat run scripts/deploy.js --network localhost

# Update backend/.env with the printed CONTRACT_ADDRESS
# Then restart the backend

# Run tests
npx hardhat test
```

---

## Demo Scenarios

| Scenario | Description | Expected |
|---|---|---|
| A | Normal INR 1L → SGD | LOW risk, RAIL_C selected, settled |
| B | INR 25L, velocity=18, new recipient | HIGH risk, ON_HOLD |
| C | Any payment to Iran | BLOCKED (sanctions) |
| D | Drain RAIL_C → submit payment | RAIL_C rejected, RAIL_B selected |

The "Drain RAIL_C Liquidity" button in the UI triggers Scenario D automatically.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/payment/process` | Full orchestration pipeline |
| POST | `/api/v1/risk/analyze` | Standalone risk scoring |
| POST | `/api/v1/fx/calculate` | FX for a specific rail |
| GET  | `/api/v1/routes/available` | Rail availability + liquidity |
| GET  | `/api/v1/control-tower/stats` | Dashboard aggregates |
| GET  | `/api/v1/control-tower/transactions` | Live transaction feed |
| PATCH| `/api/v1/rails/{id}/liquidity` | Update rail liquidity (demo) |

---

## Disclaimer

CitiFlow is a **prototype** built for demonstration purposes.

- Payment rails and liquidity pools are **simulated**
- FX rates are **mock values** with random walk
- The risk model is trained on **synthetic data** (not real Citi data)
- The smart contract runs on a **local Hardhat testnet**
- This is **not** a recreation of Citi's payment infrastructure

CitiFlow demonstrates an **intelligent orchestration layer** that could sit
above existing payment infrastructure to make routing decisions.
