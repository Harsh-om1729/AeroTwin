import numpy as np

def compute_health_index(fused_scores, p=1.0, score_max=100.0):
    """
    Converts a fused anomaly PERCENTILE (bounded [0, score_max], higher =
    more anomalous -- see aerotwin.models.fusion.ScoreFuser) into a 0-100
    Health Index: HI = 100 * (1 - (score / score_max)^p).

    This is bounded by construction (unlike an exponential decay, which
    needs an unbounded input to ever reach low HI values -- applied to a
    percentile already capped at 100, it barely moves off 100). p controls
    how fast HI falls as the score rises towards its max; calibrate it so
    the median val_healthy score maps to HI ~= 95.
    """
    norm = np.clip(fused_scores, 0, score_max) / score_max
    hi = 100 * (1 - norm ** p)
    return np.clip(hi, 0, 100)


def calibrate_p(median_score, score_max=100.0, target_hi=95.0):
    """Solves for p such that compute_health_index(median_score) == target_hi."""
    norm_median = np.clip(median_score, 1e-6, score_max - 1e-6) / score_max
    return np.log(1 - target_hi / 100.0) / np.log(norm_median)

def alert_logic(hi_series, times, threshold=50, n_consecutive=8):
    """
    Triggers an alert if HI < threshold for N consecutive windows.
    Returns boolean array of alert states matching the input series length.
    """
    alerts = np.zeros(len(hi_series), dtype=bool)
    consecutive_count = 0
    
    for i, hi in enumerate(hi_series):
        if hi < threshold:
            consecutive_count += 1
        else:
            consecutive_count = 0
            
        if consecutive_count >= n_consecutive:
            alerts[i] = True
            
    return alerts
