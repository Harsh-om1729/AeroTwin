import numpy as np
import pandas as pd

from aerotwin.health.rul import estimate_rul


def evaluate_rul_predictions(hi_series, times, fault_log, w=10, failure_threshold=50):
    """Walks each fault mission's Health Index series after onset, comparing
    the point RUL estimate at each step to the true remaining life
    (failure_t - t). Returns (per_point_df, summary_dict); the per-point
    errors double as the empirical sample for an uncertainty band around
    future RUL estimates (e.g. median +/- error std).

    hi_series / times: {mission_id: array}, aligned, for fault missions.
    fault_log: dataframe with columns mission_id, fault_start_t, failure_t.
    """
    failure_t = dict(zip(fault_log["mission_id"], fault_log["failure_t"]))
    fault_start_t = dict(zip(fault_log["mission_id"], fault_log["fault_start_t"]))

    rows = []
    for mid, hi in hi_series.items():
        if mid not in failure_t:
            continue
        t = times[mid]
        onset = fault_start_t[mid]
        onset_idx = np.searchsorted(t, onset)

        for i in range(len(t)):
            # Require a full post-onset window: right at onset the fit is
            # still mixing flat pre-fault data with 1-2 decaying points,
            # which makes the linear-trend extrapolation blow up.
            if i - onset_idx + 1 < w:
                continue
            pred = estimate_rul(hi[onset_idx: i + 1], t[onset_idx: i + 1], t[i], w=w, failure_threshold=failure_threshold)
            true_rul = failure_t[mid] - t[i]
            if not np.isfinite(pred) or true_rul <= 0:
                continue
            rows.append({
                "mission_id": mid,
                "t": t[i],
                "pred_rul_s": pred,
                "true_rul_s": true_rul,
                "error_s": pred - true_rul,
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df, {"n": 0, "mae_s": float("nan"), "bias_s": float("nan"), "error_std_s": float("nan")}

    summary = {
        "n": len(df),
        "mae_s": df["error_s"].abs().mean(),
        "bias_s": df["error_s"].mean(),
        "error_std_s": df["error_s"].std(),
    }
    return df, summary
