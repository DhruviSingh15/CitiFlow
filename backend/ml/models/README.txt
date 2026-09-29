ML model artifacts will be saved here after running:

    cd backend
    python ml/train.py

Files generated:
- risk_model.pkl     (trained + calibrated RandomForest, ~50MB)
- model_metadata.json (version, metrics, feature list)

These files are excluded from Git (.gitignore).
