import numpy as np

def estimate_rul(hi_series, times, current_time, w=10, failure_threshold=50):
    """
    Fits a linear trend to the last W windows of the Health Index.
    Extrapolates to find when HI crosses the failure_threshold.
    Returns estimated RUL in seconds.
    """
    if len(hi_series) < 2:
        return np.nan
        
    hi_series = np.asarray(hi_series, dtype=float)
    times = np.asarray(times, dtype=float)
    ok = np.isfinite(hi_series) & np.isfinite(times)
    hi_series, times = hi_series[ok], times[ok]
    if len(hi_series) < 2:
        return np.nan

    # Already at or below the failure threshold: no life remains
    if hi_series[-1] <= failure_threshold:
        return 0.0

    w = min(w, len(hi_series))
    recent_hi = hi_series[-w:]
    recent_t = times[-w:]

    # Fit linear trend: HI = m*t + c
    m, c = np.polyfit(recent_t, recent_hi, 1)
    
    # If health is improving or flat, RUL is infinite
    if m >= 0:
        return np.inf
        
    # Extrapolate: failure_threshold = m * failure_t + c
    failure_t = (failure_threshold - c) / m
    
    rul = failure_t - current_time
    return max(0, rul)
