import json
import pandas as pd
import numpy as np
import yaml
import joblib
from pathlib import Path

from aerotwin.features.residuals import compute_residuals
from aerotwin.features.windowing import FeaturePipeline
from aerotwin.models.isolation_forest import IFDetector
from aerotwin.models.pca_detector import PCADetector
from aerotwin.models.lstm_autoencoder import LSTMAEDetector
from aerotwin.models.fusion import ScoreFuser
from aerotwin.health.health_index import compute_health_index, alert_logic, calibrate_p

def load_data(data_dir, split):
    return pd.read_parquet(data_dir / f"{split}.parquet")

def load_config():
    cfg_path = Path(__file__).parent.parent.parent / "configs" / "engine_rotax912.yaml"
    with open(cfg_path, 'r') as f:
        return yaml.safe_load(f)

def main():
    # Reproducible training: same data + same seed -> same models
    np.random.seed(0)
    import torch
    torch.manual_seed(0)
    data_dir = Path(__file__).parent.parent.parent / "data"
    cfg = load_config()
    
    print("Loading data...")
    df_train = load_data(data_dir, "train_healthy")
    df_val = load_data(data_dir, "val_healthy")
    
    print("Computing residuals...")
    res_train = compute_residuals(df_train, cfg)
    res_val = compute_residuals(df_val, cfg)
    
    print("Fitting Feature Pipeline (Scaler)...")
    # Drop rows with NaNs if any
    res_train.dropna(inplace=True)
    res_val.dropna(inplace=True)
    
    pipeline = FeaturePipeline()
    pipeline.fit(res_train)
    
    print("Extracting Windows...")
    X_train_stats, _ = pipeline.transform_to_stats(res_train)
    X_val_stats, _ = pipeline.transform_to_stats(res_val)
    
    print(f"Train windows: {len(X_train_stats)}, Val windows: {len(X_val_stats)}")
    
    print("Training Isolation Forest...")
    if_model = IFDetector(contamination=0.01)
    if_model.fit(X_train_stats)
    val_if_scores = if_model.score(X_val_stats)
    
    print("Training PCA...")
    pca_model = PCADetector(variance_ratio=0.95)
    pca_model.fit(X_train_stats)
    val_pca_scores = pca_model.score(X_val_stats)
    
    print("Training LSTM Autoencoder...")
    # Get sequence data for LSTM
    X_train_seq, _ = pipeline.transform_to_sequences(res_train)
    X_val_seq, _ = pipeline.transform_to_sequences(res_val)
    
    # Simple training run
    lstm_model = LSTMAEDetector(n_feat=X_train_seq.shape[2], hidden=32, latent=8)
    lstm_model.fit(X_train_seq, X_val_seq, epochs=5, batch_size=256)
    val_lstm_scores = lstm_model.score(X_val_seq)
    
    print("Fitting Score Fuser on Validation Data...")
    fuser = ScoreFuser()
    model_names = ["IF", "PCA", "LSTM"]
    fuser.fit(model_names, [val_if_scores, val_pca_scores, val_lstm_scores])
    
    print("Calibrating Health Index...")
    fused_val = fuser.score(model_names, [val_if_scores, val_pca_scores, val_lstm_scores])

    # Calibrate p so the median val_healthy fused percentile maps to HI ~= 95.
    median_score = np.median(fused_val)
    p_calibrated = calibrate_p(median_score, target_hi=95.0)
    print(f"Calibrated p: {p_calibrated:.5f}")

    # Validate HI
    hi_val = compute_health_index(fused_val, p=p_calibrated)
    print(f"Validation HI -> Median: {np.median(hi_val):.2f}, Min: {np.min(hi_val):.2f}")

    models_dir = Path(__file__).parent.parent.parent / "models"
    models_dir.mkdir(exist_ok=True)

    joblib.dump(pipeline, models_dir / "pipeline.joblib")
    joblib.dump(if_model, models_dir / "if_model.joblib")
    joblib.dump(pca_model, models_dir / "pca_model.joblib")
    joblib.dump(lstm_model, models_dir / "lstm_model.joblib")
    joblib.dump(fuser, models_dir / "fuser.joblib")
    with open(models_dir / "metadata.json", "w") as f:
        json.dump({
            "model_names": model_names,
            "p_calibrated": p_calibrated,
            "window_size": 60,
            "stride": 10,
        }, f, indent=2)

    print(f"Models saved to {models_dir}")

if __name__ == "__main__":
    main()
