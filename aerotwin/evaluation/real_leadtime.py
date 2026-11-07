"""Full-archive NGAFID study: more healthy data, and lead time before a repair.

    python3 -m aerotwin.evaluation.real_leadtime          # development fold only -> cache/real_leadtime.json
    python3 -m aerotwin.evaluation.real_leadtime --test   # adds the test fold (a RE-USE of fold 4)

real_report uses the 11,269-flight benchmark (2 days either side of a repair).
This uses all 28,935 flights of the archive (9 to 108 days before a repair, up to 70 after,
plus repair-day flights) for two things:

  1. a healthy baseline fitted on ~2.5x more after-maintenance flights.
     Is the benchmark AUC still near chance with more data? If it is, the problem
     is not too little data.
  2. a lead-time curve: anomaly score against days to the repair. A degrading
     engine should score higher as the repair nears and drop after it. Also a
     within-repair trend test, which needs no threshold and no labels for fitting.

Folds work as in real_report. Each extra flight takes its repair group's fold;
groups with no benchmark flight (FIT_ONLY) only fit the baseline. Repair-day
("same") flights are never used for fitting: whether they flew before or after
the repair is unknown. Nothing here is tuned on fold 4. Fold 4 was already used
by real_report and real_supervised, so any --test number is a re-use of it.
"""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, wilcoxon

from aerotwin.evaluation.real_report import (DATA_DIR, OIL, ROOT, _auc, event_bootstrap, evaluate, fit,
                                             flight_scores)
from aerotwin.real_engine.feature_extraction import BLOCK_S, FIT_ONLY, find_root, load_header_all, prepare_all

BLOCKS_PATH = DATA_DIR / "real" / "ngafid_blocks_all.parquet"
STATS_PATH = DATA_DIR / "real" / "ngafid_blocks_all_stats.json"
MODEL_PATH = ROOT / "models" / "real" / "ngafid_all.joblib"
RESULTS_PATH = ROOT / "cache" / "real_leadtime.json"
SCORES = ["Fused", OIL]
# days to the repair; 0 = repair day ("same")
BINS = [(-999, -15, "<= -15"), (-14, -8, "-14..-8"), (-7, -4, "-7..-4"), (-3, -3, "-3"), (-2, -2, "-2"),
        (-1, -1, "-1"), (0, 0, "0 (repair day)"), (1, 1, "+1"), (2, 2, "+2"), (3, 3, "+3"),
        (4, 7, "+4..+7"), (8, 14, "+8..+14"), (15, 999, ">= +15")]
MIN_TREND_FLIGHTS = 4


def load():
    root = find_root(DATA_DIR)
    if BLOCKS_PATH.exists():
        blocks, stats = pd.read_parquet(BLOCKS_PATH), json.loads(STATS_PATH.read_text())
    else:
        blocks, stats = prepare_all(root, BLOCKS_PATH)
        STATS_PATH.write_text(json.dumps(stats))
    h = load_header_all(root)
    h = h[h["flight"].isin(blocks["flight"].unique())].reset_index(drop=True)
    # real_report.fit() trains on before == 0: after-repair flights only, never "same"
    h["before"] = h["before_after"].map({"before": 1, "after": 0, "same": 2})
    return blocks, h, stats


def fit_header(h):
    """FIT_ONLY flights join fold 0, which only fits the healthy baseline."""
    return h.assign(fold=h["fold"].replace(FIT_ONLY, 0))


def _bin(days):
    for lo, hi, name in BINS:
        if lo <= days <= hi:
            return name
    raise ValueError(days)


def _mean_ci(x, groups, n=500, seed=0):
    rng = np.random.default_rng(seed)
    x, groups = np.asarray(x), np.asarray(groups)
    index = [np.nonzero(groups == g)[0] for g in np.unique(groups)]
    vals = [x[np.concatenate([index[i] for i in rng.integers(0, len(index), len(index))])].mean() for _ in range(n)]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def lead_time_curve(d):
    """Mean score per days-to-repair bin, 95% CI over repair groups. Scores are
    centred on the median over after-repair flights 4+ days later, so 0 = the
    level of a freshly repaired engine."""
    d = d.assign(bin=d["date_diff"].map(_bin))
    ref = d[d["date_diff"] >= 4]
    out = []
    for _, _, name in BINS:
        g = d[d["bin"] == name]
        row = {"bin": name, "flights": len(g), "event_groups": int(g["event_group"].nunique())}
        for s in SCORES:
            x = g[s] - ref[s].median()
            row[s] = {"mean": float(x.mean()), "ci95": _mean_ci(x, g["event_group"])} if len(g) >= 20 else None
        out.append(row)
    return out


def trend_test(d):
    """Within each repair, does the score rise as the repair nears? Spearman of
    score vs date_diff over its before-flights (one rho per repair group with
    >= MIN_TREND_FLIGHTS of them on >= 3 distinct days). A real degradation signal gives
    positive rhos on average. Wilcoxon signed-rank test against 0."""
    b = d[d["before_after"] == "before"]
    out = {}
    for s in SCORES:
        rhos = []
        for _, g in b.groupby("event_group"):
            if len(g) >= MIN_TREND_FLIGHTS and g["date_diff"].nunique() >= 3:
                rho = spearmanr(g["date_diff"], g[s]).statistic
                if np.isfinite(rho):
                    rhos.append(rho)
        rhos = np.array(rhos)
        out[s] = {"repairs": len(rhos), "mean_rho": float(rhos.mean()) if len(rhos) else None,
                  "share_positive": float((rhos > 0).mean()) if len(rhos) else None,
                  "wilcoxon_p": float(wilcoxon(rhos).pvalue) if len(rhos) >= 10 else None}
    return out


def far_vs_near(d):
    """AUC of before-flights by distance: 'near' (1-2 days before) vs flights 4+
    days after the repair, and 'far' (8+ days before) vs the same after-flights.
    If wear builds up, near should separate better than far."""
    after = d[d["date_diff"] >= 4]
    out = {}
    for name, sel in {"near (-2..-1)": d["date_diff"].between(-2, -1),
                      "mid (-7..-3)": d["date_diff"].between(-7, -3),
                      "far (<= -8)": d["date_diff"] <= -8}.items():
        g = pd.concat([d[sel & (d["before_after"] == "before")], after])
        y = (g["before_after"] == "before").astype(int).to_numpy()
        out[name] = {"before_flights": int(y.sum()), "after_flights": int((y == 0).sum()),
                     **{s: {"auc": _auc(y, g[s]), "ci95": event_bootstrap(y, g[s], g["event_group"], n=300)}
                        for s in SCORES}}
    return out


def fold_report(scores, h, fold, thresholds=None):
    d = scores.merge(h, on="flight")
    d = d[d["fold"] == fold]
    bench = h[h["in_benchmark"] & (h["before"] < 2)]
    two = d[d["before"] < 2]
    y = two["before"].to_numpy()
    return {
        "flights": len(d),
        "benchmark": evaluate(scores, bench, fold, thresholds),   # same flights as real_report
        "all_before_vs_after": {"flights": len(two),
                                **{s: {"auc": _auc(y, two[s]), "ci95": event_bootstrap(y, two[s], two["event_group"])}
                                   for s in SCORES}},
        "lead_time": lead_time_curve(d),
        "trend": trend_test(d),
        "distance": far_vs_near(d),
    }


def main(test=False):
    blocks, h, stats = load()
    used = h["fold"].value_counts().to_dict()
    print(f"{stats} blocks={len(blocks):,} hours={len(blocks) * BLOCK_S / 3600:,.0f} folds={used}", flush=True)
    if MODEL_PATH.exists():
        bundle = joblib.load(MODEL_PATH)
    else:
        bundle = fit(blocks, fit_header(h))
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(bundle, MODEL_PATH)
    held = blocks[blocks["flight"].isin(h[h["fold"].isin([3, 4] if test else [3])]["flight"])]
    scores = flight_scores(bundle, held)
    fit_flights = fit_header(h).query("fold in [0, 1, 2] and before == 0")
    result = {
        "dataset": {"name": "NGAFID Aviation Maintenance Dataset (full archive)", **stats,
                    "airborne_hours_used": len(blocks) * BLOCK_S / 3600,
                    "healthy_fit_flights": int(len(fit_flights)),
                    "healthy_fit_flights_benchmark_only": int(fit_flights["in_benchmark"].sum())},
        "dev": fold_report(scores, h, 3),
    }
    if test:
        result["test"] = fold_report(scores, h, 4, {m: v["threshold"] for m, v in
                                                    result["dev"]["benchmark"]["decisions"].items()})
        result["test"]["note"] = "fold 4 re-used: already seen by real_report and real_supervised"
    RESULTS_PATH.parent.mkdir(exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(result, allow_nan=False))
    return result


if __name__ == "__main__":
    r = main("--test" in sys.argv)
    print(json.dumps(r["dataset"], indent=1))
    for split in [k for k in ("dev", "test") if k in r]:
        x = r[split]
        print(f"\n== {split}: {x['flights']} flights")
        print("benchmark flights:", {m["method"]: round(m["auc"], 3) for m in x["benchmark"]["methods"]})
        print("all before vs after:", {s: round(x["all_before_vs_after"][s]["auc"], 3) for s in SCORES})
        print(pd.DataFrame([{"bin": b["bin"], "n": b["flights"],
                             **{s: None if b[s] is None else round(b[s]["mean"], 3) for s in SCORES}}
                            for b in x["lead_time"]]).to_string(index=False))
        print("trend:", json.dumps(x["trend"]))
        print("distance:", {k: {s: round(v[s]["auc"], 3) for s in SCORES} for k, v in x["distance"].items()})
