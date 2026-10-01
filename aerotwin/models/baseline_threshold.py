import numpy as np

def baseline_alerts(df, limits):
    """
    Computes baseline threshold alerts (no ML).
    Fires if any sensor goes out of the fixed [lo, hi] bounds.
    """
    alerts = np.zeros(len(df), dtype=bool)
    
    for col, (lo, hi) in limits.items():
        if col in df.columns:
            # We use bitwise OR to aggregate alerts across all sensors
            alerts |= (df[col] < lo) | (df[col] > hi)
            
    return alerts

def get_rotax_limits(cfg):
    """
    Extracts fixed limits from the YAML configuration.
    Converts string '[VERIFY]' values to safe prototype numbers if needed.
    """
    # These should match the structure of configs/engine_rotax912.yaml
    # We provide default prototype values to prevent crashing if the user 
    # hasn't replaced [VERIFY] yet.
    
    def safe_float(val, default):
        try:
            return float(val)
        except (ValueError, TypeError):
            return default
            
    return {
        "oil_press_bar": (
            safe_float(cfg.get("oil_press", {}).get("min"), 0.8),
            safe_float(cfg.get("oil_press", {}).get("max"), 7.0)
        ),
        "oil_temp_c": (
            safe_float(cfg.get("oil_temp", {}).get("min"), 50.0),
            safe_float(cfg.get("oil_temp", {}).get("max"), 130.0)
        ),
        "cht_1": (0.0, safe_float(cfg.get("cht", {}).get("max"), 135.0)),
        "cht_2": (0.0, safe_float(cfg.get("cht", {}).get("max"), 135.0)),
        "cht_3": (0.0, safe_float(cfg.get("cht", {}).get("max"), 135.0)),
        "cht_4": (0.0, safe_float(cfg.get("cht", {}).get("max"), 135.0)),
        "egt_1": (0.0, safe_float(cfg.get("egt", {}).get("max"), 880.0)),
        "egt_2": (0.0, safe_float(cfg.get("egt", {}).get("max"), 880.0)),
        "egt_3": (0.0, safe_float(cfg.get("egt", {}).get("max"), 880.0)),
        "egt_4": (0.0, safe_float(cfg.get("egt", {}).get("max"), 880.0)),
    }
