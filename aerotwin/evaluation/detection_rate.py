import pandas as pd


def evaluate_detections(predictions, fault_log):
    """Per-mission fault detection outcome.

    predictions: {mission_id: [(t, is_alert), ...]}
    fault_log: dataframe with columns mission_id, fault_type, fault_start_t, failure_t
        (failure_t = ground-truth time the fault becomes a functional failure,
        see aerotwin.simulator.fault_injection.compute_failure_t)

    A fault counts as "detected" only if the alert fires in the actionable
    window: after the fault actually starts, and before it would have caused
    failure. Returns DataFrame[mission_id, fault_type, detected, lead_time]
    (lead_time is NaN when not detected).
    """
    rows = []
    for _, r in fault_log.iterrows():
        mid = r["mission_id"]
        alerts = predictions.get(mid)
        detected = False
        lead_time = float("nan")

        if alerts:
            valid = [
                (t, a) for t, a in alerts
                if a and r["fault_start_t"] <= t < r["failure_t"]
            ]
            if valid:
                detected = True
                lead_time = r["failure_t"] - valid[0][0]

        rows.append({
            "mission_id": mid,
            "fault_type": r["fault_type"],
            "detected": detected,
            "lead_time": lead_time,
        })

    return pd.DataFrame(rows)


def compute_detection_rate(predictions, fault_log):
    """Detection rate per fault_type: fraction of fault missions where the
    fault was caught after onset and before the engine would have failed."""
    df = evaluate_detections(predictions, fault_log)
    return df.groupby("fault_type")["detected"].mean().to_dict()
