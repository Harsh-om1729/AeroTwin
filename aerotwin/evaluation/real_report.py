"""Real-flight validation on the NGAFID dataset (Cessna 172).

    python3 -m aerotwin.evaluation.real_report          # development fold only
    python3 -m aerotwin.evaluation.real_report --test   # frozen test fold -> cache/real_results.json

Question: does the score separate flights just before unplanned maintenance
from flights just after it? Nothing is tuned on labels: all detectors learn only
from after-maintenance flights. Folds never mix:

    fold 0  after-maintenance flights  fit the healthy baseline
    fold 1  after-maintenance flights  fit scaler and detectors
    fold 2  after-maintenance flights  calibrate fusion and Health Index
    fold 3  before + after             development
    fold 4  before + after             frozen test

"After maintenance" means the reported part was fixed, not that the engine is
fault-free, and no fault time is known, so labels are per flight.
"""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from aerotwin.features.windowing import FeaturePipeline
from aerotwin.health.health_index import calibrate_p, compute_health_index
from aerotwin.models.fusion import ScoreFuser
from aerotwin.models.isolation_forest import IFDetector
from aerotwin.models.lstm_autoencoder import LSTMAEDetector
from aerotwin.models.pca_detector import PCADetector
from aerotwin.real_engine.feature_extraction import BLOCK_S, SENSORS, find_root, load_header, prepare
from aerotwin.real_engine.sim2real import HealthyBaseline, windows

ROOT = Path(__file__).parent.parent.parent
DATA_DIR = ROOT / "data"
# in a subfolder: report.inputs_mtime watches data/*.parquet for the Rotax results
BLOCKS_PATH = DATA_DIR / "real" / "ngafid_blocks.parquet"
STATS_PATH = DATA_DIR / "real" / "ngafid_blocks_stats.json"
MODEL_PATH = ROOT / "models" / "real" / "ngafid.joblib"
RESULTS_PATH = ROOT / "cache" / "real_results.json"
WINDOW, STRIDE = 30, 30   # 5 min of 10 s blocks
MODEL_NAMES = ["IF", "PCA", "LSTM"]
PUBLISHED = {"model": "ConvMHSA (supervised, trained on these labels)", "binary_accuracy": 0.761,
             "source": "Yang & Desell 2022, Table 2, mean over 5 folds"}
N_BOOT = 1000
OIL = "Low oil pressure"
DECISION_SCORES = ["Fused", OIL]


def load_blocks():
    root = find_root(DATA_DIR)
    if BLOCKS_PATH.exists():
        blocks, stats = pd.read_parquet(BLOCKS_PATH), json.loads(STATS_PATH.read_text())
    else:
        blocks, stats = prepare(root, BLOCKS_PATH)
        STATS_PATH.write_text(json.dumps(stats))
    header = load_header(root)
    return blocks, header[header["flight"].isin(blocks["flight"].unique())].reset_index(drop=True), stats


def score_windows(models, X_stats, X_seq):
    return [models["IF"].score(X_stats), models["PCA"].score(X_stats), models["LSTM"].score(X_seq)]


def fit(blocks, header):
    import torch
    np.random.seed(0)
    torch.manual_seed(0)
    after = lambda fold: blocks[blocks["flight"].isin(header[(header["fold"] == fold) & (header["before"] == 0)]["flight"])]
    base_df, det_df, cal_df = after(0), after(1), after(2)

    baseline = HealthyBaseline().fit(base_df)
    det_res = baseline.residuals(det_df)
    pipeline = FeaturePipeline()
    pipeline.fit(det_res)
    Xs, Xq, _ = windows(det_res, det_df, pipeline, WINDOW, STRIDE)
    models = {"IF": IFDetector(), "PCA": PCADetector(), "LSTM": LSTMAEDetector(Xq.shape[2], hidden=32, latent=8)}
    models["IF"].fit(Xs)
    models["PCA"].fit(Xs)
    models["LSTM"].fit(Xq, None, epochs=5, batch_size=256)

    Xs, Xq, _ = windows(baseline.residuals(cal_df), cal_df, pipeline, WINDOW, STRIDE)
    cal_scores = score_windows(models, Xs, Xq)
    fuser = ScoreFuser()
    fuser.fit(MODEL_NAMES, cal_scores)
    p = float(calibrate_p(np.median(fuser.score(MODEL_NAMES, cal_scores)), target_hi=95.0))
    return {"baseline": baseline, "pipeline": pipeline, "models": models, "fuser": fuser, "p": p}


def flight_scores(bundle, blocks):
    """Mean over each flight's windows, for every detector, the fused percentile
    and a plain residual baseline (no ML): the largest mean |z| of any channel."""
    res = bundle["baseline"].residuals(blocks)
    Xs, Xq, owner = windows(res, blocks, bundle["pipeline"], WINDOW, STRIDE)
    raw = score_windows(bundle["models"], Xs, Xq)
    n_ch = Xq.shape[2]
    d = pd.DataFrame({m: s for m, s in zip(MODEL_NAMES, raw)})
    d["Fused"] = bundle["fuser"].score(MODEL_NAMES, raw)
    d["Residual threshold"] = np.abs(Xs[:, :n_ch]).max(axis=1)
    # picked on the dev fold as the best of 11 simple scores: treat with care, a
    # repair visit may also change the oil, which would raise pressure afterwards
    d[OIL] = -Xs[:, list(res.columns).index("oil_press_bar_res")]
    d["hi"] = compute_health_index(d["Fused"].to_numpy(), p=bundle["p"])
    d["flight"] = owner
    return d.groupby("flight").mean().reset_index()


def _auc(y, s):
    return float(roc_auc_score(y, s)) if len(set(y)) == 2 else None


def event_bootstrap(y, s, groups, n=N_BOOT, seed=0):
    """95% CI resampling whole maintenance-event groups: flights around one
    repair are correlated, so resampling single flights would be too narrow."""
    rng = np.random.default_rng(seed)
    y, s, groups = np.asarray(y), np.asarray(s), np.asarray(groups)
    index = {g: np.nonzero(groups == g)[0] for g in np.unique(groups)}
    keys = list(index)
    vals = []
    for _ in range(n):
        pick = rng.integers(0, len(keys), len(keys))
        idx = np.concatenate([index[keys[i]] for i in pick])
        if len(set(y[idx])) == 2:
            vals.append(roc_auc_score(y[idx], s[idx]))
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def _decision(s, y, threshold=None):
    """Flag rates at a threshold. With none given (dev fold only), picks the one
    with the best balanced accuracy: plain accuracy just flags almost nothing."""
    balanced = lambda t: ((s[y == 1] > t).mean() + (s[y == 0] <= t).mean()) / 2
    if threshold is None:
        threshold = float(max(np.quantile(s, np.linspace(0.05, 0.95, 91)), key=balanced))
    return {"threshold": threshold, "balanced_accuracy": float(balanced(threshold)),
            "recall_before": float((s[y == 1] > threshold).mean()), "false_flag_after": float((s[y == 0] > threshold).mean())}


def evaluate(scores, header, fold, thresholds=None):
    d = scores.merge(header, on="flight")
    d = d[d["fold"] == fold]
    y = d["before"].to_numpy()
    methods = []
    for m in ["Fused", *MODEL_NAMES, "Residual threshold", OIL]:
        methods.append({"method": m, "auc": _auc(y, d[m]), "ci95": event_bootstrap(y, d[m], d["event_group"])})
    issues = []
    for issue, g in d.groupby("issue"):
        issues.append({"issue": issue, "flights": len(g), "auc": _auc(g["before"], g["Fused"]),
                       "ci95": event_bootstrap(g["before"], g["Fused"], g["event_group"], n=300)})
    thresholds = thresholds or {}
    decisions = {}
    for m in DECISION_SCORES:
        decisions[m] = _decision(d[m].to_numpy(), y, thresholds.get(m))
    return {
        "flights": len(d), "before": int(y.sum()), "after": int((y == 0).sum()),
        "event_groups": int(d["event_group"].nunique()),
        "methods": methods, "issues": issues, "decisions": decisions,
        "hi_median": {"before": float(d[y == 1]["hi"].median()), "after": float(d[y == 0]["hi"].median())},
    }


def baseline_fit(bundle, blocks, header):
    """How well the learned baseline predicts healthy flights it never saw."""
    d = blocks[blocks["flight"].isin(header[(header["fold"] == 2) & (header["before"] == 0)]["flight"])]
    pred = bundle["baseline"].predict(d)
    out = {}
    for s in SENSORS:
        e = d[s].to_numpy() - pred[s].to_numpy()
        out[s] = {"mae": float(np.abs(e).mean()), "bias": float(e.mean()), "r2": float(1 - e.var() / d[s].to_numpy().var())}
    return out


def main(test=False):
    blocks, header, stats = load_blocks()
    print(f"{stats} blocks={len(blocks):,} hours={len(blocks) * BLOCK_S / 3600:,.0f}", flush=True)
    if MODEL_PATH.exists():
        bundle = joblib.load(MODEL_PATH)
    else:
        bundle = fit(blocks, header)
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(bundle, MODEL_PATH)
    held = blocks[blocks["flight"].isin(header[header["fold"].isin([3, 4] if test else [3])]["flight"])]
    scores = flight_scores(bundle, held)
    dev = evaluate(scores, header, 3)
    result = {
        "dataset": {"name": "NGAFID Aviation Maintenance Dataset", "aircraft": "Cessna 172", **stats,
                    "airborne_hours_used": len(blocks) * BLOCK_S / 3600},
        "baseline_fit": baseline_fit(bundle, blocks, header), "published": PUBLISHED,
        "window_s": WINDOW * BLOCK_S, "dev": dev,
    }
    if test:
        result["test"] = evaluate(scores, header, 4, {m: v["threshold"] for m, v in dev["decisions"].items()})
        RESULTS_PATH.parent.mkdir(exist_ok=True)
        RESULTS_PATH.write_text(json.dumps(result, allow_nan=False))
    return result


if __name__ == "__main__":
    r = main("--test" in sys.argv)
    print(json.dumps({k: v for k, v in r.items() if k != "baseline_fit"}, indent=1))
    print(pd.DataFrame(r["baseline_fit"]).T.round(3).to_string())
