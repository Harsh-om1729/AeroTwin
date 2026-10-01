def compute_false_alarms_per_fh(predictions, fault_log, mission_durations):
    """False alarms per flight hour, counted over all time the engine was
    actually healthy:
      - the entirety of healthy missions (mission_id not in fault_log), and
      - the pre-onset portion of fault missions (before fault_start_t).

    predictions: {mission_id: [(t, is_alert), ...]} for ALL missions
    fault_log: dataframe with columns mission_id, fault_start_t
    mission_durations: {mission_id: duration_in_seconds}
    """
    onset_t = dict(zip(fault_log["mission_id"], fault_log["fault_start_t"]))

    false_alerts = 0
    healthy_seconds = 0.0

    for mid, alerts in predictions.items():
        start_t = onset_t.get(mid)  # None for healthy missions
        duration = mission_durations.get(mid, 0.0)
        healthy_seconds += duration if start_t is None else min(start_t, duration)

        for t, is_alert in alerts:
            if is_alert and (start_t is None or t < start_t):
                false_alerts += 1

    healthy_fh = healthy_seconds / 3600.0
    return false_alerts / healthy_fh if healthy_fh > 0 else 0.0
