"""Reality-gap study: how do the three detectors degrade as the digital twin
stops matching the engine, and how much does per-engine calibration recover?

    python3 -m aerotwin.evaluation.gap_study      # ~5 min on 4+ cores -> cache/gap_study.json

Design (paired): the same 30 flights (10 healthy, 5 fault types x 4) are
flown at every gap level with identical noise seeds, fault onsets and engine
identities; only the gap magnitude changes. Each flight's engine also flies
one healthy reference flight (different noise seed) used for calibration.
Every method keeps its deployed threshold, fixed before this study:

    ML ensemble     HI < 50 for 8 windows
    Bayesian twin   P(degraded) > 0.95
    CUSUM           statistic > h (calibrated on gap-0 healthy validation)

Conditions: "raw" (nominal twin, no calibration) and "calibrated"
(reference-flight offsets subtracted, see replay.estimate_calibration).
Seeds come from block 6 (600000+), disjoint from every dataset split.
"""
import json
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from aerotwin.evaluation.false_alarms import count_false_alarms
from aerotwin.evaluation.stats import clopper_pearson
from aerotwin.simulator.fault_injection import FaultInjector, compute_failure_t
from aerotwin.simulator.generate_dataset import FAULTS, generate_mission_data

LEVELS = [0.0, 0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0]
CONDITIONS = ["raw", "calibrated"]
METHODS = {"ml": "ML ensemble", "twin": "Bayesian twin", "cusum": "CUSUM"}
TRUE_CYL = {"injector_abnormality": 1, "misfire": 2}
N_HEALTHY, RUNS_PER_FAULT, SEED_BASE = 10, 4, 6
MISSION_S = 3600


def _flights():
    rng = np.random.default_rng(SEED_BASE)
    flights = [{"id": f"gh_{i}", "fault": None, "onset": None, "rate": None,
                "seed": SEED_BASE * 100_000 + i} for i in range(N_HEALTHY)]
    for fi, (ft, rate) in enumerate(FAULTS):
        for m in range(RUNS_PER_FAULT):
            flights.append({"id": f"gf_{ft}_{m}", "fault": ft, "onset": int(rng.integers(500, 2000)), "rate": rate,
                            "seed": SEED_BASE * 100_000 + 1000 + fi * 100 + m})
    return flights


def _compact(tl):
    return [{
        "t": r["t"], "ml": r["alert"], "cusum": r["cusum_alarm"],
        "twin": r["twin"]["p_degraded"] > 0.95, "map": r["twin"]["map"],
        "rul": r["twin"]["rul"], "diag": r["diagnosis"]["fault"] if r["diagnosis"] else None,
    } for r in tl]


def _run_one(args):
    flight, gap = args
    import torch
    torch.set_num_threads(1)
    from aerotwin.inference.replay import compute_mission_timeline, estimate_calibration, get_bundle
    bundle = get_bundle()
    engine = flight["seed"] + 50_000  # engine identity, shared with the reference flight
    np.random.seed(flight["seed"] % 2**32)
    inj = FaultInjector(flight["fault"], flight["onset"], flight["rate"]) if flight["fault"] else None
    df = generate_mission_data("GAP", flight["id"], "standard", flight["seed"], inj, gap=gap, engine_seed=engine).set_index("t")
    ref = generate_mission_data("GAP", flight["id"] + "_ref", "standard", flight["seed"] + 77, None, gap=gap,
                                engine_seed=engine).set_index("t")
    cal = estimate_calibration(ref, bundle.cfg)
    return flight["id"], gap, {
        "raw": _compact(compute_mission_timeline(df, bundle)),
        "calibrated": _compact(compute_mission_timeline(df, bundle, calibration=cal)),
    }


def _metrics(flights, timelines):
    """timelines: {flight_id: compact timeline} for one (level, condition)."""
    log = pd.DataFrame([{"mission_id": f["id"], "fault_start_t": f["onset"]} for f in flights if f["fault"]])
    durations = {f["id"]: MISSION_S for f in flights}
    out = {}
    for m in METHODS:
        preds = {fid: [(x["t"], x[m]) for x in tl] for fid, tl in timelines.items()}
        fa = count_false_alarms(preds, log, durations)
        # Severity of false alarming: fraction of healthy time spent in alarm
        # (event counts saturate at one per flight once a method alarms all flight)
        onset = {f["id"]: f["onset"] for f in flights if f["fault"]}
        healthy_flags = [x[m] for f in flights for x in timelines[f["id"]]
                         if f["id"] not in onset or x["t"] < onset[f["id"]]]
        det, delays, diag_ok, cover = [], [], [], []
        for f in (f for f in flights if f["fault"]):
            fail = compute_failure_t(f["fault"], f["onset"], f["rate"])
            tl = timelines[f["id"]]
            # a detection is a NEW alarm that starts after onset; an alarm that
            # was already on before the fault began earns no credit
            hit = next((x for k, x in enumerate(tl)
                        if x[m] and (k == 0 or not tl[k - 1][m]) and f["onset"] <= x["t"] < fail), None)
            det.append(hit is not None)
            if hit:
                delays.append(hit["t"] - f["onset"])
                if m == "twin":
                    diag_ok.append(hit["map"]["fault"] == f["fault"] and hit["map"]["cylinder"] == TRUE_CYL.get(f["fault"]))
                    cover += [x["rul"]["p5"] <= fail - x["t"] <= x["rul"]["p95"]
                              for x in tl if x["twin"] and x["rul"] and hit["t"] <= x["t"] < fail]
                elif m == "ml":
                    diag_ok.append(hit["diag"] == f["fault"])
        k, n = int(sum(det)), len(det)
        out[m] = {
            "detection": {"k": k, "n": n, "rate": k / n, "ci95": clopper_pearson(k, n)},
            "median_delay_s": float(np.median(delays)) if delays else None,
            "false_alarm_events": fa["events"],
            "healthy_alarm_fraction": float(np.mean(healthy_flags)) if healthy_flags else 0.0,
            "false_alarms_per_fh": fa["per_fh"],
            "false_alarms_ci95": fa["ci95"],
            "healthy_hours": fa["healthy_hours"],
            "diagnosis": float(np.mean(diag_ok)) if diag_ok else None,
            "coverage90": float(np.mean(cover)) if cover else None,
        }
    return out


def run(workers=None):
    flights = _flights()
    tasks = [(f, g) for g in LEVELS for f in flights]
    results = {}
    with ProcessPoolExecutor(max_workers=workers or max(1, (os.cpu_count() or 2) - 1)) as ex:
        for fid, gap, tl in ex.map(_run_one, tasks, chunksize=2):
            results[(fid, gap)] = tl
    study = {"levels": LEVELS, "methods": METHODS, "n_healthy": N_HEALTHY, "n_fault": len(FAULTS) * RUNS_PER_FAULT,
             "conditions": {}}
    for cond in CONDITIONS:
        study["conditions"][cond] = [
            {"gap": g, **_metrics(flights, {f["id"]: results[(f["id"], g)][cond] for f in flights})} for g in LEVELS
        ]
    return study


if __name__ == "__main__":
    from aerotwin.inference.replay import ROOT
    s = run()
    (ROOT / "cache").mkdir(exist_ok=True)
    json.dump(s, open(ROOT / "cache" / "gap_study.json", "w"))
    for cond, rows in s["conditions"].items():
        print(f"\n== {cond} ==")
        for r in rows:
            print(f"gap {r['gap']:.2f} | " + " | ".join(
                f"{m}: det {r[m]['detection']['k']}/{r[m]['detection']['n']} FA {r[m]['false_alarm_events']} "
                f"inAlarm {r[m]['healthy_alarm_fraction']:.0%} "
                f"delay {r[m]['median_delay_s']}" for m in METHODS))
