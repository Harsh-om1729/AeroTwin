import pandas as pd


def first_new_alarm_index(flags, times, onset, failure):
    """Index of the first NEW alarm (rising edge) inside the actionable window
    [onset, failure), or None. An alarm that was already on before the fault
    began is a false alarm and earns no credit; one raised after the engine
    would have failed is too late. Shared by every detection metric so the
    report, AMOC, gap study and per-mission rows agree on what "detected" means."""
    prev = False
    for i, (f, t) in enumerate(zip(flags, times)):
        f = bool(f)
        if f and not prev and onset <= t < failure:
            return i
        prev = f
    return None


def evaluate_detections(predictions, fault_log):
    """Per-mission fault detection outcome.

    predictions: {mission_id: [(t, is_alert), ...]}
    fault_log: dataframe with columns mission_id, fault_type, fault_start_t, failure_t
        (failure_t = ground-truth time the fault becomes a functional failure,
        see aerotwin.simulator.fault_injection.compute_failure_t)

    A fault counts as "detected" only if a NEW alert fires in the actionable
    window: after the fault actually starts, and before it would have caused
    failure (see first_new_alarm_index). Returns DataFrame[mission_id, fault_type, detected, lead_time]
    (lead_time is NaN when not detected).
    """
    rows = []
    for _, r in fault_log.iterrows():
        mid = r["mission_id"]
        alerts = predictions.get(mid)
        detected = False
        lead_time = float("nan")

        if alerts:
            times = [t for t, _ in alerts]
            i = first_new_alarm_index([a for _, a in alerts], times, r["fault_start_t"], r["failure_t"])
            if i is not None:
                detected = True
                lead_time = r["failure_t"] - times[i]

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
