import pandas as pd

from aerotwin.health.health_index import alert_logic
from aerotwin.evaluation.detection_rate import evaluate_detections
from aerotwin.evaluation.lead_time import summarize_lead_times
from aerotwin.evaluation.false_alarms import compute_false_alarms_per_fh


def compute_tradeoff_curve(hi_series, times, fault_log, mission_durations,
                            thresholds=range(50, 96, 5), n_consecutive=3):
    """Sweeps the HI alert threshold and reports, at each operating point,
    the resulting false-alarms-per-flight-hour vs. detection rate vs. median
    lead time -- the standard way to pick an alert threshold (the ROC/PR-curve
    analog for a fault-detection system: tightening the threshold buys
    earlier/more detections at the cost of more false alarms).

    hi_series / times: {mission_id: array} of Health Index values and their
    aligned timestamps, for ALL missions (healthy + fault).
    fault_log: dataframe with columns mission_id, fault_type, fault_start_t, failure_t.
    mission_durations: {mission_id: duration_in_seconds}, for ALL missions.
    """
    rows = []
    for thr in thresholds:
        predictions = {
            mid: list(zip(times[mid], alert_logic(hi_series[mid], times[mid],
                                                   threshold=thr, n_consecutive=n_consecutive)))
            for mid in hi_series
        }
        detections = evaluate_detections(predictions, fault_log)
        lead_times = detections.dropna(subset=["lead_time"]).set_index("mission_id")["lead_time"].to_dict()
        lead_summary = summarize_lead_times(lead_times)

        rows.append({
            "threshold": thr,
            "detection_rate": detections["detected"].mean(),
            "false_alarms_per_fh": compute_false_alarms_per_fh(predictions, fault_log, mission_durations),
            "median_lead_time_s": lead_summary["median_s"],
        })

    return pd.DataFrame(rows).sort_values("threshold").reset_index(drop=True)
