"""Grounding layer for the maintenance copilot.

Every fact the copilot may state comes from one of these read-only functions,
which read the digital twin's own outputs (fleet timelines, validation report,
engine limits). The Claude path calls them as tools; the offline engine calls
them directly, so both paths always report the same numbers.

All functions return plain JSON-serialisable dicts. Unknown aircraft or fault
types return {"error": ...} instead of raising, so a model's bad tool call can
never crash the backend.
"""
from __future__ import annotations

from aerotwin.diagnosis.fault_diagnosis import FAULT_ACTIONS, FAULT_LABELS
from aerotwin.xai.attribution import LABELS as SENSOR_LABELS

DECISION_RANK = {"NO-GO": 0, "CAUTION": 1, "GO": 2}

# Suggested follow-up checks per fault mode. Deliberately generic, and always
# paired with a sensor-plausibility check: a failed probe can mimic a fault.
FOLLOW_UP_CHECKS = {
    "lubrication": [
        "Confirm the low oil pressure with an independent mechanical gauge to rule out a sensor fault.",
        "Check oil level and condition (colour, metal particles) and the filter element.",
        "If confirmed, check the oil pump drive and the pressure relief valve before any further engine run.",
    ],
    "cooling_degradation": [
        "Check coolant level and look for leaks.",
        "Inspect the radiator, cowling inlets and baffles for blockage or damage.",
        "Cross-check CHT probes against each other; all four rising together points to cooling, not a probe.",
    ],
    "injector_abnormality": [
        "Verify the EGT probe on that cylinder first (a loose probe can read high).",
        "Leak-check the intake manifold joints and rubber boots on that cylinder.",
        "Check carburettor synchronisation and jetting on the side feeding that cylinder.",
    ],
    "misfire": [
        "Inspect and test the spark plugs on the flagged cylinder.",
        "Check ignition leads and connectors for that cylinder.",
        "Compare with the next magneto/ignition-circuit check on run-up.",
    ],
    "abnormal_vibration": [
        "Check propeller balance and the propeller attachment.",
        "Inspect the engine mounts and rubber dampers.",
        "Plan a borescope or oil-analysis check for bearing wear.",
    ],
}

MANUAL_NOTE = ("Prototype decision support from a simulated digital twin. Follow the approved Rotax "
               "maintenance documentation for all procedures and limits.")


def clock(t):
    t = int(round(t))
    return f"T+{t // 60:02d}:{t % 60:02d}"


def hypothesis_name(key):
    """Particle-filter hypothesis key ('healthy', 'misfire:2', ...) -> readable name."""
    if key == "healthy":
        return "Healthy"
    fault, _, cyl = key.partition(":")
    return fault_name(fault, int(cyl) if cyl else None)


def fault_name(fault, cylinder=None):
    label = FAULT_LABELS.get(fault, fault)
    return f"{label}, cylinder {cylinder}" if cylinder else label


class Evidence:
    """fleet: list of {"id", "callsign", "mission_id", ...}
    timelines: {aircraft_id: [window rows from compute_mission_timeline]}
    report: validation report (cache/results.json), may be None
    gap_study: reality-gap study (cache/gap_study.json), may be None
    cfg: engine config (configs/engine_rotax912.yaml)
    """

    def __init__(self, fleet, timelines, cfg, report=None, gap_study=None):
        self.fleet = {e["id"]: e for e in fleet}
        self.order = [e["id"] for e in fleet]
        self.timelines = timelines
        self.cfg = cfg
        self.report = report
        self.gap_study = gap_study

    # ------------------------------------------------------------------ utils
    def resolve(self, aircraft_id):
        if not aircraft_id:
            return None
        a = str(aircraft_id).strip().upper().replace(" ", "")
        if not a.startswith("AT-") and a.startswith("AT"):
            a = "AT-" + a[2:]
        if a.isdigit():
            a = "AT-" + a
        return a if a in self.fleet else None

    def _row(self, aircraft_id, t=None):
        tl = self.timelines[aircraft_id]
        if t is None:
            return tl[-1]
        before = [r for r in tl if r["t"] <= float(t)]
        return before[-1] if before else tl[0]

    def _unknown(self, aircraft_id):
        return {"error": f"Unknown aircraft '{aircraft_id}'. Known aircraft: {', '.join(self.order)}."}

    # ------------------------------------------------------------- the tools
    def fleet_overview(self):
        rows = []
        for a in self.order:
            tl = self.timelines[a]
            last = tl[-1]
            first_alert = next((r["t"] for r in tl if r["alert"]), None)
            twin_det = next((r for r in tl if r["twin"]["p_degraded"] > 0.95), None)
            diag = next((r["diagnosis"] for r in reversed(tl) if r["diagnosis"]), None)
            tw = last["twin"]
            rows.append({
                "aircraft_id": a,
                "callsign": self.fleet[a].get("callsign"),
                "decision": last["advisor"]["decision"],
                "health_index": round(sorted(r["hi"] for r in tl[-5:])[2], 1),
                "flight_time": clock(last["t"]),
                "most_likely_fault": fault_name(tw["map"]["fault"], tw["map"]["cylinder"]) if tw["p_degraded"] > 0.95
                else None,
                "signature_check_fault": fault_name(diag["fault"], diag["cylinder"]) if diag else None,
                "first_ml_alert": clock(first_alert) if first_alert is not None else None,
                "first_twin_detection": clock(twin_det["t"]) if twin_det else None,
            })
        rows.sort(key=lambda r: (DECISION_RANK.get(r["decision"], 3), r["health_index"]))
        return {"aircraft": rows, "note": "Each aircraft's last flight is a simulated test flight."}

    def aircraft_status(self, aircraft_id, t=None):
        a = self.resolve(aircraft_id)
        if a is None:
            return self._unknown(aircraft_id)
        r = self._row(a, t)
        tl = self.timelines[a]
        tw = r["twin"]
        cfg = self.cfg

        readings = {
            "oil_pressure_bar": {"measured": round(r["oil_press_bar"], 2), "healthy_twin": round(r["exp"]["oil_press_bar"], 2),
                                 "limits": f"{cfg['oil_press']['min']}-{cfg['oil_press']['max']} bar"},
            "oil_temp_c": {"measured": round(r["oil_temp_c"], 1), "healthy_twin": round(r["exp"]["oil_temp_c"], 1),
                           "limit_max": cfg["oil_temp"]["max"]},
            "cht_c": {f"cyl_{i}": round(r[f"cht_{i}"], 1) for i in range(1, 5)} | {"healthy_twin": round(r["exp"]["cht"], 1),
                                                                                  "limit_max": cfg["cht"]["max"]},
            "egt_c": {f"cyl_{i}": round(r[f"egt_{i}"], 1) for i in range(1, 5)} | {"healthy_twin": round(r["exp"]["egt"], 1),
                                                                                  "limit_max": cfg["egt"]["max"]},
            "vibration_g_rms": {"measured": round(r["vib_rms_g"], 2), "healthy_twin": round(r["exp"]["vib_rms_g"], 2)},
            "rpm": round(r["rpm"]),
        }

        twin = {
            "p_component_degraded": round(tw["p_degraded"], 4),
            "top_hypotheses": [
                {"hypothesis": hypothesis_name(k), "probability": round(v, 4)}
                for k, v in sorted(tw["posterior"].items(), key=lambda kv: -kv[1])[:3]
            ],
            "p_failure_within_next_60min_mission": round(tw["p_fail_horizon"], 4),
        }
        if tw["p_degraded"] > 0.95:
            twin["most_likely_fault"] = fault_name(tw["map"]["fault"], tw["map"]["cylinder"])
            twin["component_health"] = {"median": round(tw["health"]["p50"], 3), "ci90_low": round(tw["health"]["p5"], 3),
                                        "ci90_high": round(tw["health"]["p95"], 3), "scale": "1 = as new"}
            if tw["rate_per_min"] is not None:
                twin["degradation_rate_pct_per_min"] = round(100 * tw["rate_per_min"], 2)
            if tw["rul"]:
                twin["remaining_useful_life_min"] = {"median": round(tw["rul"]["p50"] / 60, 1),
                                                     "ci90_low": round(tw["rul"]["p5"] / 60, 1),
                                                     "ci90_high": round(tw["rul"]["p95"] / 60, 1),
                                                     "to": "the simulated functional-failure threshold"}

        diag = r["diagnosis"]
        signature = None
        if diag:
            signature = {"fault": fault_name(diag["fault"], diag["cylinder"]), "confidence": diag["confidence"],
                         "evidence": diag["evidence"], "action": diag["action"]}

        # explanation: this window's, or -- only while the engine is still flagged -- the
        # latest flagged window at or before t (a past noise blip must not explain a healthy engine)
        flagged = r["alert"] or r["alert_latched"] or r["hi_smooth"] < 80
        xr = r if r.get("xai") else (next((x for x in reversed([w for w in tl if w["t"] <= r["t"]]) if x.get("xai")), None)
                                     if flagged else None)
        xai = None
        if xr:
            x = xr["xai"]
            top = [kv for kv in sorted(x["share"].items(), key=lambda kv: -kv[1]) if kv[1] >= 5.0][:4]
            xai = {
                "window": clock(xr["t"]),
                "top_sensors": [{"sensor": SENSOR_LABELS.get(c, c), "share_of_anomaly_evidence_pct": v} for c, v in top],
                "counterfactual": {
                    "sensor": SENSOR_LABELS.get(x["counterfactual"]["channel"], x["counterfactual"]["channel"]),
                    "fused_percentile_now": x["base"]["fused"],
                    "fused_percentile_if_sensor_healthy": x["counterfactual"]["fused_without"],
                },
            }

        return {
            "aircraft_id": a,
            "callsign": self.fleet[a].get("callsign"),
            "time": clock(r["t"]),
            "time_is_end_of_flight": t is None,
            "flight_phase": r.get("phase"),
            "decision": r["advisor"]["decision"],
            "decision_reasons": r["advisor"]["reasons"],
            "health_index": {"smoothed": round(r["hi_smooth"], 1), "scale": "0 failed - 100 as new"},
            "ml_ensemble": {"alert": r["alert"], "alert_latched": r["alert_latched"], "degrading": r["degrading"],
                            "fused_anomaly_percentile": r["fused"]},
            "bayesian_twin": twin,
            "signature_check": signature,
            "explainable_ai": xai,
            "readings": readings,
            "data_note": "Simulated test flight replayed through the digital twin.",
        }

    def event_timeline(self, aircraft_id):
        a = self.resolve(aircraft_id)
        if a is None:
            return self._unknown(aircraft_id)
        ev = []
        phase = diag = dec = None
        degr = alert = twin_det = False
        n_alerts = 0
        for r in self.timelines[a]:
            if r.get("phase") and r["phase"] != phase:
                ev.append((r["t"], f"Flight phase: {r['phase']}"))
                phase = r["phase"]
            if r["twin"]["p_degraded"] > 0.95 and not twin_det:
                m = r["twin"]["map"]
                ev.append((r["t"], f"Bayesian twin detects {fault_name(m['fault'], m['cylinder'])} "
                                   f"(P={r['twin']['p_degraded']:.2f}, health {r['twin']['health']['p50']:.2f})"))
                twin_det = True
            if r["degrading"] and not degr:
                ev.append((r["t"], f"Health Index degrading (HI {r['hi']:.0f} < 80, sustained)"))
            degr = r["degrading"]
            if r["diagnosis"] and r["diagnosis"]["fault"] != diag:
                ev.append((r["t"], f"Signature check: {fault_name(r['diagnosis']['fault'], r['diagnosis']['cylinder'])}"))
                diag = r["diagnosis"]["fault"]
            if r["alert"] and not alert:
                n_alerts += 1
                ev.append((r["t"], "ML ensemble alert raised (HI < 50 for 8 windows)" if n_alerts == 1
                           else "ML ensemble alert raised again after briefly clearing"))
            alert = r["alert"]
            if r["advisor"]["decision"] != dec:
                if dec is not None:
                    ev.append((r["t"], f"Mission advisor: {dec} -> {r['advisor']['decision']}"))
                dec = r["advisor"]["decision"]
        return {"aircraft_id": a, "events": [{"time": clock(t), "event": e} for t, e in ev]}

    def engine_limits(self):
        c = self.cfg
        return {
            "engine": c.get("variant"),
            "rpm": {"idle_min": c["rpm"]["idle"], "max_continuous": c["rpm"]["max_continuous"],
                    "max_takeoff_5min": c["rpm"]["max_takeoff"]},
            "oil_pressure_bar": {"min": c["oil_press"]["min"], "max": c["oil_press"]["max"], "normal": c["oil_press"]["normal"]},
            "oil_temp_c": {"min": c["oil_temp"]["min"], "max": c["oil_temp"]["max"], "normal": c["oil_temp"]["normal"]},
            "cht_max_c": c["cht"]["max"],
            "egt_max_c": c["egt"]["max"],
            "source": c["rpm"].get("source"),
        }

    def maintenance_actions(self, fault_type):
        key = str(fault_type or "").strip().lower().replace(" ", "_")
        aliases = {"injector": "injector_abnormality", "lean_cylinder": "injector_abnormality", "lean": "injector_abnormality",
                   "cooling": "cooling_degradation", "bearing": "abnormal_vibration", "vibration": "abnormal_vibration",
                   "oil": "lubrication", "ignition": "misfire"}
        key = aliases.get(key, key)
        if key not in FAULT_ACTIONS:
            return {"error": f"Unknown fault type '{fault_type}'. Known: {', '.join(FAULT_ACTIONS)}."}
        return {"fault": FAULT_LABELS[key], "primary_action": FAULT_ACTIONS[key],
                "suggested_checks": FOLLOW_UP_CHECKS[key], "note": MANUAL_NOTE}

    def validation_summary(self):
        if not self.report:
            return {"error": "Validation report not available."}
        r = self.report
        s, m, tw = r["summary"], r["metrics"], r["twin"]
        cov = next((c for c in tw["coverage"] if c["nominal"] == 90), None)
        out = {
            "dataset": f"Simulated dataset v{r.get('dataset_version')}: {s['n_fault_missions']} fault + "
                       f"{s['n_healthy_missions']} healthy test flights, evaluated once",
            "ml_ensemble": {
                "faults_detected": f"{s['detection']['k']}/{s['detection']['n']}",
                "false_alarm_events": f"{m['false_alarms']['events']} in {m['false_alarms']['healthy_hours']:.0f} healthy flight-hours",
                "diagnosis_correct": f"{s['diagnosis']['k']}/{s['diagnosis']['n']}",
            },
            "bayesian_twin": {
                "faults_detected": f"{tw['detection']['k']}/{tw['detection']['n']}",
                "diagnosis_correct": f"{tw['diagnosis']['k']}/{tw['diagnosis']['n']}",
                "false_alarm_events": tw["false_alarms"]["events"],
                "rul_90pct_interval_coverage": round(cov["empirical"], 3) if cov else None,
            },
        }
        if r.get("xai"):
            h = r["xai"]["top1_hit"]["ensemble"]
            out["explanations_top_sensor_correct"] = f"{h['k']}/{h['n']}"
        if self.gap_study:
            usable = {}
            for cond, rows in self.gap_study["conditions"].items():
                usable[cond] = {}
                for meth in ("ml", "twin", "cusum"):
                    last = None
                    for row in rows:
                        if row[meth]["healthy_alarm_fraction"] <= 0.05 and row[meth]["detection"]["rate"] >= 0.9:
                            last = row["gap"]
                        else:
                            break
                    usable[cond][meth] = last
            out["robustness_largest_usable_reality_gap"] = usable
        out["limitations"] = [
            "All data is simulated; the main test uses a twin that matches the simulator exactly (an upper bound).",
            "When the engine departs from the twin, every method degrades; per-engine calibration is required.",
            "The twin's RUL intervals become over-confident under model mismatch.",
            "Single faults only; sensor faults are not yet modelled.",
        ]
        return out


TOOL_SPECS = [
    {
        "name": "get_fleet_overview",
        "description": "List every aircraft in the fleet with its Go/No-Go decision, Health Index, most likely fault and "
                       "first detection times, sorted from highest to lowest risk. Use for fleet-wide or prioritisation questions.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_aircraft_status",
        "description": "Full digital-twin evidence for one aircraft at one moment of its last flight: Go/No-Go decision and "
                       "reasons, Health Index, ML-ensemble alert state, Bayesian twin fault probabilities, component health "
                       "and remaining useful life (with 90% intervals), rule-based signature check, explainable-AI sensor "
                       "attribution and key sensor readings vs the healthy twin and engine limits. Omit t_seconds for the end "
                       "of the flight.",
        "input_schema": {
            "type": "object",
            "properties": {
                "aircraft_id": {"type": "string", "description": "Aircraft ID such as AT-104"},
                "t_seconds": {"type": "integer", "description": "Optional flight time in seconds (0-3600)"},
            },
            "required": ["aircraft_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_event_timeline",
        "description": "Chronological events of an aircraft's last flight: phase changes, Bayesian-twin detection, Health "
                       "Index degradation, ML alerts, diagnosis and Go/No-Go changes, with flight times.",
        "input_schema": {
            "type": "object",
            "properties": {"aircraft_id": {"type": "string", "description": "Aircraft ID such as AT-104"}},
            "required": ["aircraft_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_engine_limits",
        "description": "Rotax 912 S/ULS operating limits used by the advisor (RPM, oil pressure, oil temperature, CHT, EGT) "
                       "and their source.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_maintenance_actions",
        "description": "Recommended primary action and suggested follow-up checks for a fault type: lubrication, "
                       "cooling_degradation, injector_abnormality (lean cylinder), misfire or abnormal_vibration.",
        "input_schema": {
            "type": "object",
            "properties": {"fault_type": {"type": "string", "description": "One of the fault types listed above"}},
            "required": ["fault_type"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_validation_summary",
        "description": "How reliable the system is: detection, false-alarm, diagnosis and uncertainty-calibration results "
                       "on the simulated test set, the reality-gap robustness study, and known limitations.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


def run_tool(ev, name, args):
    """Execute one tool call safely. Never raises: bad input becomes an error dict."""
    args = args if isinstance(args, dict) else {}
    try:
        if name == "get_fleet_overview":
            return ev.fleet_overview()
        if name == "get_aircraft_status":
            t = args.get("t_seconds")
            t = None if t is None else max(0, min(3600, int(t)))
            return ev.aircraft_status(args.get("aircraft_id"), t)
        if name == "get_event_timeline":
            return ev.event_timeline(args.get("aircraft_id"))
        if name == "get_engine_limits":
            return ev.engine_limits()
        if name == "get_maintenance_actions":
            return ev.maintenance_actions(args.get("fault_type"))
        if name == "get_validation_summary":
            return ev.validation_summary()
        return {"error": f"Unknown tool '{name}'."}
    except (TypeError, ValueError, KeyError) as e:
        return {"error": f"Invalid arguments for {name}: {e}"}
