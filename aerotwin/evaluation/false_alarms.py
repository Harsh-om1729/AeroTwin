from aerotwin.evaluation.stats import poisson_rate_ci


def count_false_alarms(predictions, fault_log, mission_durations):
    """False-alarm EVENTS over all time the engine was actually healthy:
      - the entirety of healthy missions (mission_id not in fault_log), and
      - the pre-onset portion of fault missions (before fault_start_t).

    An event is one rising edge of the alert flag (healthy -> alerting). A
    single alarm that stays on for many consecutive windows is ONE false
    alarm, not one per window.

    predictions: {mission_id: [(t, is_alert), ...]} for ALL missions,
        time-ordered per mission
    fault_log: dataframe with columns mission_id, fault_start_t
    mission_durations: {mission_id: duration_in_seconds}

    Returns dict(events, healthy_hours, per_fh, ci95).
    """
    onset_t = dict(zip(fault_log["mission_id"], fault_log["fault_start_t"]))

    events = 0
    healthy_seconds = 0.0
    for mid, alerts in predictions.items():
        start_t = onset_t.get(mid)  # None for healthy missions
        duration = mission_durations.get(mid, 0.0)
        healthy_seconds += duration if start_t is None else min(start_t, duration)

        prev = False
        for t, is_alert in alerts:
            if start_t is not None and t >= start_t:
                break
            if is_alert and not prev:
                events += 1
            prev = bool(is_alert)

    hours = healthy_seconds / 3600.0
    return {
        "events": events,
        "healthy_hours": hours,
        "per_fh": events / hours if hours > 0 else 0.0,
        "ci95": poisson_rate_ci(events, hours) if hours > 0 else (0.0, 0.0),
    }


def compute_false_alarms_per_fh(predictions, fault_log, mission_durations):
    """False-alarm events per healthy flight-hour (see count_false_alarms)."""
    return count_false_alarms(predictions, fault_log, mission_durations)["per_fh"]
