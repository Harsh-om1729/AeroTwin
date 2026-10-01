from aerotwin.evaluation.detection_rate import evaluate_detections
from aerotwin.evaluation.lead_time import summarize_lead_times
from aerotwin.evaluation.false_alarms import count_false_alarms
from aerotwin.evaluation.stats import clopper_pearson


def compute_metrics(predictions, fault_log, mission_durations):
    """
    predictions: {mission_id: [(t, is_alert), ...]} for ALL missions
    fault_log: dataframe with columns mission_id, fault_type, fault_start_t,
        failure_t (see aerotwin.simulator.fault_injection.compute_failure_t)
    mission_durations: {mission_id: duration_in_seconds}, for ALL missions
    """
    detections = evaluate_detections(predictions, fault_log)
    lead_times = detections.dropna(subset=["lead_time"]).set_index("mission_id")["lead_time"].to_dict()

    fa = count_false_alarms(predictions, fault_log, mission_durations)
    k, n = int(detections["detected"].sum()), len(detections)
    return {
        "detection_rate": detections.groupby("fault_type")["detected"].mean().to_dict(),
        "detection_overall": {"detected": k, "n": n, "ci95": clopper_pearson(k, n)},
        "lead_time": summarize_lead_times(lead_times),
        "false_alarms_per_fh": fa["per_fh"],
        "false_alarms": fa,
    }
