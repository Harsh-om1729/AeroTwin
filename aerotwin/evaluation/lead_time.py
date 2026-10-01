import numpy as np

from aerotwin.evaluation.detection_rate import evaluate_detections


def compute_lead_times(predictions, fault_log):
    """Lead time in seconds (failure_t - first_alert_t) for each detected
    fault mission. Returns {mission_id: lead_time_s}; undetected missions are
    omitted (use compute_detection_rate for the miss rate)."""
    df = evaluate_detections(predictions, fault_log)
    return df.dropna(subset=["lead_time"]).set_index("mission_id")["lead_time"].to_dict()


def summarize_lead_times(lead_times):
    """lead_times: dict of {mission_id: lead_time_s} or a plain iterable of values."""
    values = np.asarray(
        list(lead_times.values()) if isinstance(lead_times, dict) else list(lead_times),
        dtype=float,
    )
    if len(values) == 0:
        return {"n": 0, "median_s": float("nan"), "p10_s": float("nan"), "p90_s": float("nan")}

    return {
        "n": len(values),
        "median_s": float(np.median(values)),
        "p10_s": float(np.percentile(values, 10)),
        "p90_s": float(np.percentile(values, 90)),
    }
