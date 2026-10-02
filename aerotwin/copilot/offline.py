"""Offline copilot: answers without any external API.

Used automatically whenever the Claude API cannot answer (no key, no credit,
no network, rate limit, refusal, timeout) and on demand. It recognises the
common maintenance questions by keyword and composes the answer from the same
evidence functions the Claude path uses as tools, so the numbers are always
identical; only the phrasing is simpler. It never guesses: an unrecognised
question gets an honest "here is what I can answer" reply.
"""
from __future__ import annotations

import re

from aerotwin.copilot.evidence import MANUAL_NOTE

INTENTS = [  # checked in order; first match wins
    ("reliability", ["reliab", "accura", "trust", "confiden", "validat", "how good", "false alarm", "real engine",
                     "real world", "real-world", "limitation", "proof", "evidence that"]),
    ("limits", ["limit", "redline", "red line", "maximum", "minimum", "allowed"]),
    # fleet-wide wording must win over per-aircraft intents ("which aircraft should we inspect first?")
    ("fleet", ["fleet", "all aircraft", "which aircraft", "every aircraft", "most urgent", "priorit",
               "how many aircraft", "grounded aircraft"]),
    ("timeline", ["timeline", "when did", "events", "what happened", "history", "sequence", "first detect"]),
    ("xai", ["sensor", "explain the ml", "explainable", "which reading", "caused the alert", "evidence share",
             "xai", "why did the ml", "why did the model", "attribution"]),
    ("rul", ["rul", "remaining", "how long", "time to fail", "until fail", "life left", "when will", "how much time"]),
    ("maintenance", ["inspect", "check first", "what should", "fix", "repair", "maintenance", "action", "do next",
                     "procedure", "replace", "technician", "work order"]),
    ("fleet_weak", ["overview", "worst", "summary"]),  # fleet only when no aircraft is named
]
AIRCRAFT_RE = re.compile(r"\bAT[\s-]?(\d{3})\b", re.IGNORECASE)
CYL_RE = re.compile(r"\bcylinder (\d)\b")


def detect_intent(question):
    q = question.lower()
    for name, words in INTENTS:
        if any(w in q for w in words):
            return name
    return "status"


def extract_aircraft(question):
    m = AIRCRAFT_RE.search(question)
    return f"AT-{m.group(1)}" if m else None


def _pct(p):
    return f"{100 * p:.0f}%"


# ---------------------------------------------------------------- composers
def _fleet(ev):
    data = ev.fleet_overview()
    rows = data["aircraft"]
    grounded = [r for r in rows if r["decision"] == "NO-GO"]
    lines = [f"**{len(grounded)} of {len(rows)} aircraft are NO-GO** after their last flight; "
             f"{sum(r['decision'] == 'GO' for r in rows)} are cleared (GO). Highest risk first:", ""]
    for r in rows:
        fault = r["most_likely_fault"] or r["signature_check_fault"]
        lines.append(f"- **{r['aircraft_id']}** ({r['callsign']}): **{r['decision']}**, Health Index {r['health_index']}"
                     + (f", most likely fault **{fault}**" if fault else ", no fault signature")
                     + (f", twin detection {r['first_twin_detection']}" if r["first_twin_detection"] else ""))
    lines += ["", "Ask about any aircraft (for example \"Why is AT-104 grounded?\") for the full evidence."]
    return "\n".join(lines), ["get_fleet_overview"]


def _status(ev, a, t):
    s = ev.aircraft_status(a, t)
    if "error" in s:
        return s["error"], ["get_aircraft_status"]
    tw = s["bayesian_twin"]
    when = "at the end of its last flight" if s["time_is_end_of_flight"] else f"at {s['time']}"
    lines = [f"**{s['aircraft_id']} ({s['callsign']}) is {s['decision']}** {when} (flight phase: {s['flight_phase']}).", ""]
    lines.append("### Why")
    lines += [f"- {r}" for r in s["decision_reasons"]]
    if tw.get("most_likely_fault"):
        h = tw["component_health"]
        lines += ["", "### Most likely fault",
                  f"- Bayesian twin: **{tw['most_likely_fault']}** (probability {_pct(tw['top_hypotheses'][0]['probability'])})",
                  f"- Estimated component health {h['median']} (90% interval {h['ci90_low']}–{h['ci90_high']}, 1 = as new)"]
        if "remaining_useful_life_min" in tw:
            rul = tw["remaining_useful_life_min"]
            lines.append("- Failure threshold already reached" if rul["ci90_high"] == 0 else
                         f"- Remaining useful life about {rul['median']} min (90% interval {rul['ci90_low']}–{rul['ci90_high']} min)")
    if s["signature_check"]:
        lines.append(f"- Signature check agrees: {s['signature_check']['fault']} ({s['signature_check']['evidence']})")
    ml = s["ml_ensemble"]
    if (ml["alert"] or ml["alert_latched"] or ml["degrading"]) and s["explainable_ai"] and s["explainable_ai"]["top_sensors"]:
        top = s["explainable_ai"]["top_sensors"][0]
        lines.append(f"- The ML ensemble's alert is driven mainly by **{top['sensor']}** "
                     f"({top['share_of_anomaly_evidence_pct']:.0f}% of the anomaly evidence)")
    if not tw.get("most_likely_fault") and not s["signature_check"]:
        lines += ["", f"No fault signature: the Bayesian twin gives P(component degraded) = {_pct(tw['p_component_degraded'])}, "
                      f"and the ML ensemble's anomaly percentile is {s['ml_ensemble']['fused_anomaly_percentile']:.0f}."]
    if s["signature_check"]:
        lines += ["", f"**Recommended action:** {s['signature_check']['action']}"]
    return "\n".join(lines), ["get_aircraft_status"]


def _maintenance(ev, a, t):
    s = ev.aircraft_status(a, t)
    if "error" in s:
        return s["error"], ["get_aircraft_status"]
    tw = s["bayesian_twin"]
    # the Bayesian twin's hypothesis first, the signature check as a second opinion
    candidates = [tw.get("most_likely_fault"), (s["signature_check"] or {}).get("fault")]
    key = None
    for k in ("lubrication", "cooling_degradation", "injector_abnormality", "misfire", "abnormal_vibration"):
        label = ev.maintenance_actions(k)["fault"]
        if any(c and c.startswith(label) for c in candidates):
            key = k
            break
    if key is None:
        return (f"**{s['aircraft_id']} shows no fault signature** ({s['decision']}), so there is no targeted inspection "
                f"to recommend. Continue routine maintenance per the Rotax documentation."), ["get_aircraft_status"]
    m = ev.maintenance_actions(key)
    cyl = next((CYL_RE.search(c) for c in candidates if c and CYL_RE.search(c)), None)
    cyl_note = f" on cylinder {cyl.group(1)}" if cyl else ""
    lines = [f"**{s['aircraft_id']}: inspect for {m['fault'].lower()}{cyl_note}** ({s['decision']}).", "",
             f"**Primary action:** {m['primary_action']}", "", "**Suggested checks, in order:**"]
    lines += [f"{i}. {c}" for i, c in enumerate(m["suggested_checks"], start=1)]
    lines += ["", f"_{MANUAL_NOTE}_"]
    return "\n".join(lines), ["get_aircraft_status", "get_maintenance_actions"]


def _rul(ev, a, t):
    s = ev.aircraft_status(a, t)
    if "error" in s:
        return s["error"], ["get_aircraft_status"]
    tw = s["bayesian_twin"]
    if "remaining_useful_life_min" not in tw:
        return (f"**No remaining-useful-life estimate for {s['aircraft_id']}** at {s['time']}: the Bayesian twin does "
                f"not see a degrading component (P = {_pct(tw['p_component_degraded'])}), so there is nothing to "
                f"extrapolate. Decision: **{s['decision']}**."), ["get_aircraft_status"]
    rul = tw["remaining_useful_life_min"]
    head = (f"**{s['aircraft_id']} has already reached the failure threshold** at {s['time']}."
            if rul["ci90_high"] == 0 else
            f"**{s['aircraft_id']}: about {rul['median']} min of remaining useful life** at {s['time']} "
            f"(90% interval {rul['ci90_low']}–{rul['ci90_high']} min).")
    lines = [head, "",
             f"- Component: {tw['most_likely_fault']}, health {tw['component_health']['median']} "
             f"(1 = as new), falling about {tw.get('degradation_rate_pct_per_min', '?')}% per minute",
             f"- Probability of failure within the next 60-minute mission: {_pct(tw['p_failure_within_next_60min_mission'])}",
             "- RUL is measured to the simulator's functional-failure threshold; under model mismatch the intervals "
             "become over-confident (see the robustness study)."]
    return "\n".join(lines), ["get_aircraft_status"]


def _xai(ev, a, t):
    s = ev.aircraft_status(a, t)
    if "error" in s:
        return s["error"], ["get_aircraft_status"]
    x = s["explainable_ai"]
    if not x or not x["top_sensors"]:
        return (f"**The ML ensemble has not flagged {s['aircraft_id']}** at {s['time']}, so there is no anomaly to "
                f"explain (anomaly percentile {s['ml_ensemble']['fused_anomaly_percentile']:.0f})."), ["get_aircraft_status"]
    lines = [f"**For {s['aircraft_id']} the ML alert is driven by {x['top_sensors'][0]['sensor']}** "
             f"(window {x['window']}). Share of the anomaly evidence per sensor:", ""]
    lines += [f"- {e['sensor']}: {e['share_of_anomaly_evidence_pct']:.0f}%" for e in x["top_sensors"]]
    cf = x["counterfactual"]
    lines += ["", f"If the {cf['sensor']} residual had been healthy, the fused anomaly percentile would fall from "
                  f"{cf['fused_percentile_now']:.0f} to {cf['fused_percentile_if_sensor_healthy']:.0f}.",
              "Method: each sensor is reset to its healthy value and the three models are re-scored. "
              "Shares can add up to more than 100% because some sensors overlap (for example EGT 1 and the EGT spread)."]
    return "\n".join(lines), ["get_aircraft_status"]


def _timeline(ev, a):
    d = ev.event_timeline(a)
    if "error" in d:
        return d["error"], ["get_event_timeline"]
    lines = [f"**Key events in {d['aircraft_id']}'s last flight:**", ""]
    lines += [f"- {e['time']}: {e['event']}" for e in d["events"]]
    return "\n".join(lines), ["get_event_timeline"]


def _limits(ev):
    L = ev.engine_limits()
    lines = [f"**Operating limits used by the advisor ({L['engine']}):**", "",
             f"- RPM: idle ≥ {L['rpm']['idle_min']}, max continuous {L['rpm']['max_continuous']}, "
             f"max take-off {L['rpm']['max_takeoff_5min']} (5 min)",
             f"- Oil pressure: {L['oil_pressure_bar']['min']}–{L['oil_pressure_bar']['max']} bar "
             f"(normal {L['oil_pressure_bar']['normal'][0]}–{L['oil_pressure_bar']['normal'][1]})",
             f"- Oil temperature: {L['oil_temp_c']['min']}–{L['oil_temp_c']['max']} °C "
             f"(normal {L['oil_temp_c']['normal'][0]}–{L['oil_temp_c']['normal'][1]})",
             f"- CHT: max {L['cht_max_c']} °C",
             f"- EGT: max {L['egt_max_c']} °C", "", f"Source: {L['source']}."]
    return "\n".join(lines), ["get_engine_limits"]


def _reliability(ev):
    v = ev.validation_summary()
    if "error" in v:
        return v["error"], ["get_validation_summary"]
    ml, tw = v["ml_ensemble"], v["bayesian_twin"]
    lines = [f"**On simulated test flights the system is strong, but it has not been validated on a real engine.** "
             f"{v['dataset']}.", "",
             f"- ML ensemble: {ml['faults_detected']} faults detected, false-alarm events {ml['false_alarm_events']}, "
             f"diagnosis {ml['diagnosis_correct']}",
             f"- Bayesian twin: {tw['faults_detected']} detected, {tw['diagnosis_correct']} correct diagnosis, "
             f"{tw['false_alarm_events']} false-alarm events; 90% RUL interval coverage "
             f"{_pct(tw['rul_90pct_interval_coverage']) if tw['rul_90pct_interval_coverage'] is not None else 'n/a'}"]
    if v.get("explanations_top_sensor_correct"):
        lines.append(f"- Explanations: top-ranked sensor physically correct in {v['explanations_top_sensor_correct']} flights")
    if v.get("robustness_largest_usable_reality_gap"):
        g = v["robustness_largest_usable_reality_gap"]
        lines.append(f"- Robustness: with per-engine calibration the twin stays usable up to reality gap "
                     f"{g['calibrated']['twin']}, the ML ensemble up to {g['calibrated']['ml']}, CUSUM up to "
                     f"{g['calibrated']['cusum']}")
    lines += ["", "**Limitations:**"] + [f"- {x}" for x in v["limitations"]]
    return "\n".join(lines), ["get_validation_summary"]


HELP = ("I can answer questions about the fleet and each aircraft from the digital-twin data, for example:\n\n"
        "- \"Which aircraft should we inspect first?\"\n- \"Why is AT-104 grounded?\"\n"
        "- \"What should the technician check on AT-107?\"\n- \"How much remaining life does AT-105 have?\"\n"
        "- \"Which sensors caused the alert on AT-108?\"\n- \"What happened during AT-102's flight?\"\n"
        "- \"What are the engine limits?\"\n- \"How reliable is this system?\"")


def answer_offline(ev, question, aircraft_id=None, t=None):
    """Returns (markdown answer, list of evidence functions used)."""
    question = (question or "").strip()
    if not question:
        return HELP, []
    intent = detect_intent(question)
    named = extract_aircraft(question)
    a = ev.resolve(named) if named else ev.resolve(aircraft_id)
    if named and a is None:
        return ev._unknown(named)["error"], []
    if named and named != aircraft_id:
        t = None  # the dashboard time refers to the other aircraft

    if intent == "fleet_weak":
        intent = "status" if named else "fleet"
    if intent == "fleet":
        return _fleet(ev)
    if intent == "limits":
        return _limits(ev)
    if intent == "reliability":
        return _reliability(ev)
    if a is None:
        text, used = _fleet(ev)
        return ("No aircraft selected, so here is the fleet view.\n\n" + text), used
    if intent == "timeline":
        return _timeline(ev, a)
    if intent == "xai":
        return _xai(ev, a, t)
    if intent == "rul":
        return _rul(ev, a, t)
    if intent == "maintenance":
        return _maintenance(ev, a, t)
    return _status(ev, a, t)
