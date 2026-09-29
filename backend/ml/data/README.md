## CitiFlow ML — Training Data

### Option A: PaySim (Recommended for best model quality)

1. Go to https://www.kaggle.com/datasets/ealaxi/paysim1
2. Download `PS_20174392719_1491204439457_log.csv`
3. Save it to this directory: `backend/ml/data/`

PaySim is a synthetic financial transaction dataset (~6.3M rows, ~490MB).
It was created for academic fraud-detection research and is the base for
CitiFlow's risk model.

### Option B: Auto-generated synthetic data

If PaySim CSV is not present, `train.py` automatically generates
200,000 synthetic rows with similar statistical properties.
This is sufficient for a prototype demo.

### Disclaimer

All data used in CitiFlow training is synthetic.
The model is a prototype for demonstrating risk-scoring logic.
It is NOT trained on real Citi transaction data.
It is NOT a real fraud detection system.
