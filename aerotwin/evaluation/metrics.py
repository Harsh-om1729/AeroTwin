from aerotwin.evaluation.detection_rate import evaluate_detections
from aerotwin.evaluation.lead_time import summarize_lead_times
from aerotwin.evaluation.false_alarms import compute_false_alarms_per_fh


def compute_metrics(predictions, fault_log, mission_durations):
    """
    predictions: {mission_id: [(t, is_alert), ...]} for ALL missions
    fault_log: dataframe with columns mission_id, fault_type, fault_start_t,
        failure_t (see aerotwin.simulator.fault_injection.compute_failure_t)
    mission_durations: {mission_id: duration_in_seconds}, for ALL missions
    """
    detections = evaluate_detections(predictions, fault_log)
    lead_times = detections.dropna(subset=["lead_time"]).set_index("mission_id")["lead_time"].to_dict()

    return {
        "detection_rate": detections.groupby("fault_type")["detected"].mean().to_dict(),
        "lead_time": summarize_lead_times(lead_times),
        "false_alarms_per_fh": compute_false_alarms_per_fh(predictions, fault_log, mission_durations),
    }
