"""Builds the full validation report shown on the dashboard's Validation page
and caches it to cache/results.json (the backend loads the cache instead of
re-running ~150 missions through the pipeline on every start-up).

    python3 -m aerotwin.evaluation.report        # rebuild the cache

Everything here is evaluated on held-out data the models never trained on:
  - test_healthy : 60 healthy missions, airframes 8-10, hot-weather profile
  - test_fault   : 60 fault missions (5 fault types x 12), airframes 8-10
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from aerotwin.evaluation.detection_rate import evaluate_detections
from aerotwin.evaluation.metrics import compute_metrics
from aerotwin.features.residuals import compute_residuals
from aerotwin.health.health_index import alert_logic, calibrate_p, compute_health_index
from aerotwin.inference.replay import DATA_DIR, ROOT, compute_mission_timeline, get_bundle, load_mission_df
from aerotwin.simulator.fault_injection import degrade

CACHE_PATH = ROOT / "cache" / "results.json"
MISSION_S = 3600
FAULT_TYPES = ["lubrication", "cooling_degradation", "injector_abnormality", "misfire", "abnormal_vibration"]
# Cylinder each fault mode is injected on (see aerotwin.simulator.fault_injection)
TRUE_CYLINDER = {"injector_abnormality": 1, "misfire": 2}
TWIN_P = 0.95          # Bayesian twin declares a fault when P(degraded) exceeds this
ALPHA = 0.2            # alpha-lambda accuracy band: prediction within +-20 % of true RUL


def _mission_ids(split):
    return pd.read_parquet(DATA_DIR / f"{split}.parquet", columns=["mission_id"])["mission_id"].unique()


def _single_model_p(bundle):
    """Calibrates a Health-Index exponent for each detector on its own (same
    rule as the fused HI: median healthy-validation window -> HI 95), so the
    ablation compares like with like."""
    df_val = pd.read_parquet(DATA_DIR / "val_healthy.parquet")
    percs = {n: [] for n in bundle.model_names}
    # window per mission so windows never straddle two missions
    for _, m in df_val.groupby("mission_id"):
        g = compute_residuals(m.set_index("t").sort_index(), bundle.cfg).dropna()
        Xs, _ = bundle.pipeline.transform_to_stats(g, bundle.window_size, bundle.stride)
        Xq, _ = bundle.pipeline.transform_to_sequences(g, bundle.window_size, bundle.stride)
        if len(Xs) == 0:
            continue
        for name, sc in zip(bundle.model_names,
                            [bundle.if_model.score(Xs), bundle.pca_model.score(Xs), bundle.lstm_model.score(Xq)]):
            dist = bundle.fuser.val_scores[name]
            percs[name].append(np.searchsorted(dist, sc) / len(dist) * 100)
    return {n: float(calibrate_p(np.median(np.concatenate(v)), target_hi=95.0)) for n, v in percs.items()}


def build_report():
    bundle = get_bundle()
    fault_log = pd.read_csv(DATA_DIR / "fault_log.csv")
    truth = fault_log.set_index("mission_id")

    timelines = {}
    for mid in fault_log["mission_id"]:
        timelines[mid] = compute_mission_timeline(load_mission_df("test_fault", mid), bundle)
    healthy_ids = list(_mission_ids("test_healthy"))
    for mid in healthy_ids:
        timelines[mid] = compute_mission_timeline(load_mission_df("test_healthy", mid), bundle)
    durations = {mid: MISSION_S for mid in timelines}

    # ---- 1. Headline detection metrics (fused model) ----------------------
    predictions = {mid: [(r["t"], r["alert"]) for r in tl] for mid, tl in timelines.items()}
    metrics = compute_metrics(predictions, fault_log, durations)
    det = evaluate_detections(predictions, fault_log)

    # ---- 2. Ablation: each detector alone vs the fused ensemble -----------
    p_single = _single_model_p(bundle)
    ablation = []
    for name in bundle.model_names + ["Fused"]:
        preds = {}
        for mid, tl in timelines.items():
            if name == "Fused":
                hi = np.array([r["hi"] for r in tl])
            else:
                hi = compute_health_index(np.array([r["scores"][name] for r in tl]), p=p_single[name])
            t = np.array([r["t"] for r in tl])
            preds[mid] = list(zip(t, alert_logic(hi, t, threshold=50, n_consecutive=8)))
        m = compute_metrics(preds, fault_log, durations)
        rates = list(m["detection_rate"].values())
        ablation.append({
            "model": {"IF": "Isolation Forest", "PCA": "PCA (SPE)", "LSTM": "LSTM Autoencoder"}.get(name, "Fused ensemble"),
            "detection_rate": float(np.mean(rates)),
            "median_lead_s": m["lead_time"]["median_s"],
            "false_alarms_per_fh": m["false_alarms_per_fh"],
        })

    # ---- 3. Fault diagnosis (isolation) accuracy --------------------------
    labels = FAULT_TYPES + ["none"]
    confusion = {a: {b: 0 for b in labels} for a in FAULT_TYPES}
    cyl_ok, cyl_n = 0, 0
    per_mission = []
    for mid, r in truth.iterrows():
        tl = timelines[mid]
        first_alert = next((x for x in tl if x["alert"] and x["t"] >= r["fault_start_t"]), None)
        diag = first_alert["diagnosis"] if first_alert else None
        pred = diag["fault"] if diag else "none"
        confusion[r["fault_type"]][pred] += 1
        if r["fault_type"] in TRUE_CYLINDER and pred == r["fault_type"]:
            cyl_n += 1
            cyl_ok += int(diag["cylinder"] == TRUE_CYLINDER[r["fault_type"]])
        d = det.set_index("mission_id").loc[mid]
        per_mission.append({
            "mission_id": mid,
            "fault_type": r["fault_type"],
            "fault_start_t": float(r["fault_start_t"]),
            "failure_t": float(r["failure_t"]),
            "first_alert_t": first_alert["t"] if first_alert else None,
            "detected": bool(d["detected"]),
            "lead_time_s": None if pd.isna(d["lead_time"]) else float(d["lead_time"]),
            "diagnosed_as": pred,
            "cylinder": diag["cylinder"] if diag else None,
        })
    n_correct = sum(confusion[f][f] for f in FAULT_TYPES)

    # ---- 4. RUL accuracy vs ground truth ----------------------------------
    rul_pairs = []
    for mid, r in truth.iterrows():
        for x in timelines[mid]:
            if x["rul_s"] is not None and r["fault_start_t"] <= x["t"] < r["failure_t"]:
                rul_pairs.append({"true_s": float(r["failure_t"] - x["t"]), "pred_s": float(x["rul_s"]),
                                  "fault_type": r["fault_type"]})
    rul_err = np.array([p["pred_s"] - p["true_s"] for p in rul_pairs])
    # thin out for plotting
    step = max(1, len(rul_pairs) // 400)

    # ---- 5. Healthy HI distribution (false-alarm margin) ------------------
    healthy_hi = np.concatenate([[x["hi"] for x in timelines[m]] for m in healthy_ids])
    hist, edges = np.histogram(healthy_hi, bins=20, range=(0, 100))

    # ---- 6. Example HI traces, one per fault type, aligned to onset -------
    traces = {}
    for ft in FAULT_TYPES:
        mid = fault_log[fault_log["fault_type"] == ft]["mission_id"].iloc[0]
        t0 = truth.loc[mid, "fault_start_t"]
        traces[ft] = [{"dt": round(x["t"] - t0), "hi": round(x["hi_smooth"], 1)}
                      for x in timelines[mid] if -300 <= x["t"] - t0 <= 1500]

    twin = _evaluate_twin(timelines, truth, healthy_ids, per_mission)

    report = {
        "twin": twin,
        "metrics": metrics,
        "summary": {
            "n_fault_missions": int(len(fault_log)),
            "n_healthy_missions": len(healthy_ids),
            "healthy_flight_hours": float(sum(min(truth["fault_start_t"].get(m, MISSION_S), MISSION_S)
                                              for m in timelines) / 3600),
            "overall_detection_rate": float(det["detected"].mean()),
            "diagnosis_accuracy": n_correct / len(fault_log),
            "cylinder_accuracy": cyl_ok / cyl_n if cyl_n else None,
            "rul_mae_s": float(np.mean(np.abs(rul_err))) if len(rul_err) else None,
            "rul_median_abs_err_s": float(np.median(np.abs(rul_err))) if len(rul_err) else None,
        },
        "ablation": ablation,
        "confusion": confusion,
        "confusion_labels": labels,
        "per_mission": per_mission,
        "rul_scatter": rul_pairs[::step],
        "healthy_hi_hist": [{"bin": f"{int(edges[i])}-{int(edges[i + 1])}", "count": int(hist[i])}
                            for i in range(len(hist))],
        "traces": traces,
    }
    return report


def _evaluate_twin(timelines, truth, healthy_ids, per_mission):
    """Flagship evaluation: Bayesian particle-filter twin vs the ML ensemble
    on the same held-out flights."""
    ml_alert = {m["mission_id"]: m["first_alert_t"] for m in per_mission}
    detect_rows, h_err, h_trace = [], [], {}
    cover = {50: [], 80: [], 90: []}
    rul_twin_err, rul_lin_err, alpha_twin, alpha_lin = [], [], [], []
    fan = {}
    false_windows, healthy_s = 0, 0.0

    for mid, r in truth.iterrows():
        tl = timelines[mid]
        t0, fail, ft = r["fault_start_t"], r["failure_t"], r["fault_type"]
        shape = "lin" if ft == "misfire" else "exp"
        healthy_s += min(t0, MISSION_S)
        false_windows += sum(1 for x in tl if x["t"] < t0 and x["twin"]["p_degraded"] > TWIN_P)
        det = next((x for x in tl if x["t"] >= t0 and x["twin"]["p_degraded"] > TWIN_P), None)
        m = det["twin"]["map"] if det else None
        detect_rows.append({
            "mission_id": mid, "fault_type": ft,
            "twin_delay_s": det["t"] - t0 if det else None,
            "ml_delay_s": ml_alert[mid] - t0 if ml_alert[mid] is not None else None,
            "twin_detected": bool(det and det["t"] < fail),
            "twin_diag_ok": bool(m and m["fault"] == ft and m["cylinder"] == TRUE_CYLINDER.get(ft)),
        })
        if not det:
            continue
        for x in tl:
            if not (det["t"] <= x["t"] < fail):
                continue
            tw = x["twin"]
            h_err.append(abs(tw["health"]["p50"] - degrade(x["t"], t0, r["severity"], shape)))
            true = fail - x["t"]
            if tw["rul"]:
                q = tw["rul"]
                cover[50].append(q["p25"] <= true <= q["p75"])
                cover[80].append(q["p10"] <= true <= q["p90"])
                cover[90].append(q["p5"] <= true <= q["p95"])
                # compare both estimators on the same instants
                if x["rul_s"] is not None:
                    rul_twin_err.append(abs(q["p50"] - true))
                    rul_lin_err.append(abs(x["rul_s"] - true))
                    alpha_twin.append(abs(q["p50"] - true) <= ALPHA * true)
                    alpha_lin.append(abs(x["rul_s"] - true) <= ALPHA * true)
        # one example health trace + RUL fan per fault type
        if ft not in h_trace:
            pts = [x for x in tl if t0 - 120 <= x["t"] <= min(fail + 60, MISSION_S)]
            h_trace[ft] = [{
                "dt": round(x["t"] - t0),
                "true": round(degrade(x["t"], t0, r["severity"], shape), 4),
                "p5": round(x["twin"]["health"]["p5"], 4) if x["twin"]["p_degraded"] > 0.5 else 1.0,
                "p50": round(x["twin"]["health"]["p50"], 4) if x["twin"]["p_degraded"] > 0.5 else 1.0,
                "p95": round(x["twin"]["health"]["p95"], 4) if x["twin"]["p_degraded"] > 0.5 else 1.0,
            } for x in pts]
            fan[ft] = [{
                "dt": round(x["t"] - t0), "true": round((fail - x["t"]) / 60, 2),
                **{k: round(v / 60, 2) for k, v in x["twin"]["rul"].items()},
            } for x in pts if x["twin"]["rul"] and x["twin"]["p_degraded"] > TWIN_P and x["t"] < fail]

    for mid in healthy_ids:
        healthy_s += MISSION_S
        false_windows += sum(1 for x in timelines[mid] if x["twin"]["p_degraded"] > TWIN_P)

    d = pd.DataFrame(detect_rows)
    by_type = []
    for ft in FAULT_TYPES:
        g = d[d["fault_type"] == ft]
        by_type.append({
            "fault_type": ft,
            "twin_delay_s": float(g["twin_delay_s"].median()),
            "ml_delay_s": float(g["ml_delay_s"].median()),
            "twin_diag_acc": float(g["twin_diag_ok"].mean()),
        })
    med = lambda xs: float(np.median(xs)) if xs else None
    return {
        "detection_rate": float(d["twin_detected"].mean()),
        "diagnosis_accuracy": float(d["twin_diag_ok"].mean()),
        "median_delay_s": float(d["twin_delay_s"].median()),
        "ml_median_delay_s": float(d["ml_delay_s"].median()),
        "false_alarms_per_fh": false_windows / (healthy_s / 3600),
        "health_mae": float(np.mean(h_err)),
        "coverage": [{"nominal": k, "empirical": float(np.mean(v))} for k, v in cover.items()],
        "n_rul_points": len(cover[90]),
        "rul_median_abs_err_s": {"twin": med(rul_twin_err), "linear": med(rul_lin_err)},
        "alpha_lambda": {"alpha": ALPHA, "twin": float(np.mean(alpha_twin)), "linear": float(np.mean(alpha_lin))},
        "by_type": by_type,
        "health_traces": h_trace,
        "rul_fans": fan,
    }


def load_or_build(rebuild=False):
    models_mtime = (ROOT / "models" / "metadata.json").stat().st_mtime
    if not rebuild and CACHE_PATH.exists() and CACHE_PATH.stat().st_mtime > models_mtime:
        return json.load(open(CACHE_PATH))
    report = build_report()
    CACHE_PATH.parent.mkdir(exist_ok=True)
    json.dump(report, open(CACHE_PATH, "w"))
    return report


if __name__ == "__main__":
    r = load_or_build(rebuild=True)
    twin = {k: v for k, v in r["twin"].items() if k not in ("health_traces", "rul_fans")}
    print(json.dumps({k: r[k] for k in ["metrics", "summary", "ablation"]} | {"twin": twin}, indent=2))
