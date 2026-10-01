"""Mission Go / Caution / No-Go advisor.

Combines four independent evidence sources into one operator decision:
  1. Hard limits  -- Rotax 912 S/ULS operating limits from the engine config
                     (manufacturer redlines; exceeding one is always NO-GO).
  2. Health Index -- sustained alert (NO-GO) or sustained degradation (CAUTION).
  3. Prognostics  -- sustained degradation (CAUTION), with the projected time
                     to the alert threshold reported against the planned
                     mission length.
  4. Bayesian twin -- posterior probability of failure within the planned
                     mission from the particle-filter health twin (NO-GO at
                     >= 10%), or CAUTION when it is confident a component
                     is degraded.

Advisory only: a prototype decision-support aid, not a certified system.
"""

from aerotwin.diagnosis.fault_diagnosis import FAULT_LABELS


def check_limits(row, cfg):
    """Returns a list of human-readable redline exceedances for one telemetry row."""
    out = []
    rpm = row.get("rpm", 0) or 0
    oil_p = row.get("oil_press_bar")
    oil_t = row.get("oil_temp_c")
    if oil_p is not None:
        # min oil pressure only applies with the engine running above idle
        if rpm > cfg["rpm"]["idle"] and oil_p < cfg["oil_press"]["min"]:
            out.append(f"Oil pressure {oil_p:.2f} bar below minimum {cfg['oil_press']['min']} bar")
        if oil_p > cfg["oil_press"]["max"]:
            out.append(f"Oil pressure {oil_p:.2f} bar above maximum {cfg['oil_press']['max']} bar")
    if oil_t is not None and oil_t > cfg["oil_temp"]["max"]:
        out.append(f"Oil temperature {oil_t:.0f} °C above limit {cfg['oil_temp']['max']} °C")
    for i in range(1, 5):
        c = row.get(f"cht_{i}")
        if c is not None and c > cfg["cht"]["max"]:
            out.append(f"CHT cyl {i} {c:.0f} °C above limit {cfg['cht']['max']} °C")
        e = row.get(f"egt_{i}")
        if e is not None and e > cfg["egt"]["max"]:
            out.append(f"EGT cyl {i} {e:.0f} °C above limit {cfg['egt']['max']} °C")
    if rpm > cfg["rpm"]["max_takeoff"]:
        out.append(f"RPM {rpm:.0f} above max take-off {cfg['rpm']['max_takeoff']}")
    return out


def advise(row, cfg, planned_mission_s=3600.0):
    """row: one timeline row (telemetry + hi + alert + degrading + rul_s).

    Returns {"decision": "GO"|"CAUTION"|"NO-GO", "reasons": [...]}.
    """
    reasons = []
    decision = "GO"

    limits = check_limits(row, cfg)
    if limits:
        decision = "NO-GO"
        reasons += limits

    if row.get("alert"):
        decision = "NO-GO"
        reasons.append(f"Sustained Health Index alert (HI {row['hi']:.0f} < 50)")
    elif row.get("alert_latched"):
        decision = "NO-GO"
        reasons.append("Health alert latched earlier this flight – ground for inspection before next mission")

    # Prognostics alone escalates to CAUTION, not NO-GO: a linear-trend RUL
    # over a short degrading run is too noisy to ground an aircraft on its
    # own (it would flicker GO/NO-GO on brief healthy dips). Grounding needs
    # the sustained-alert evidence above.
    if decision == "GO" and row.get("degrading"):
        decision = "CAUTION"
        reasons.append(f"Health degrading (HI {row['hi']:.0f} < 80, sustained) – schedule inspection")
    # Bayesian health twin: probability-of-failure based decision
    tw = row.get("twin")
    if tw and tw["p_degraded"] >= 0.95:
        m = tw["map"]
        name = FAULT_LABELS[m["fault"]] + (f" (cyl {m['cylinder']})" if m["cylinder"] else "")
        h = tw["health"]["p50"]
        if tw["p_fail_horizon"] >= 0.10:
            decision = "NO-GO"
            reasons.append(f"Bayesian twin: P(failure within {planned_mission_s / 60:.0f} min mission) = "
                           f"{tw['p_fail_horizon'] * 100:.0f}% \u2013 {name}, health {h:.2f}")
        else:
            if decision == "GO":
                decision = "CAUTION"
            reasons.append(f"Bayesian twin: {name} degraded, health {h:.2f} \u2013 schedule inspection")

    rul = row.get("rul_s")
    if rul is not None and rul < planned_mission_s:
        reasons.append(f"Projected to reach alert threshold in ≈{rul / 60:.0f} min (< planned {planned_mission_s / 60:.0f} min mission)")

    if not reasons:
        reasons.append("All residuals within healthy bounds; no limit exceedance")
    return {"decision": decision, "reasons": reasons}
