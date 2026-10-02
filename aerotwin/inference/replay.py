import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml

from aerotwin.features.residuals import compute_residuals
from aerotwin.health.health_index import compute_health_index, alert_logic
from aerotwin.health.rul import estimate_rul
from aerotwin.diagnosis.fault_diagnosis import diagnose
from aerotwin.advisor.mission_advisor.go_nogo import advise
from aerotwin.twin.particle_filter import HealthParticleFilter
from aerotwin.xai.attribution import explain

ROOT = Path(__file__).parent.parent.parent
MODELS_DIR = ROOT / "models"
DATA_DIR = ROOT / "data"
CONFIG_PATH = ROOT / "configs" / "engine_rotax912.yaml"

TELEMETRY_COLS = [
    "rpm", "throttle_pct", "altitude_ft", "oil_press_bar", "oil_temp_c",
    "cht_1", "cht_2", "cht_3", "cht_4", "egt_1", "egt_2", "egt_3", "egt_4",
    "vib_rms_g", "fuel_flow_lph",
]


class ModelBundle:
    """Loads the trained models + feature pipeline persisted by
    aerotwin.evaluation.train_models, once, for reuse across replay requests."""

    def __init__(self):
        if not (MODELS_DIR / "metadata.json").exists():
            raise FileNotFoundError(
                f"No trained models found in {MODELS_DIR}. Run "
                "`python3 -m aerotwin.evaluation.train_models` first."
            )
        self.cfg = yaml.safe_load(open(CONFIG_PATH))
        self.pipeline = joblib.load(MODELS_DIR / "pipeline.joblib")
        self.if_model = joblib.load(MODELS_DIR / "if_model.joblib")
        self.pca_model = joblib.load(MODELS_DIR / "pca_model.joblib")
        self.lstm_model = joblib.load(MODELS_DIR / "lstm_model.joblib")
        self.fuser = joblib.load(MODELS_DIR / "fuser.joblib")

        meta = json.load(open(MODELS_DIR / "metadata.json"))
        self.model_names = meta["model_names"]
        self.p_calibrated = meta["p_calibrated"]
        self.window_size = meta["window_size"]
        self.stride = meta["stride"]


_bundle = None


def get_bundle():
    global _bundle
    if _bundle is None:
        _bundle = ModelBundle()
    return _bundle


def list_missions():
    """Enumerates mission_ids available for replay (healthy + fault), with
    ground-truth fault info where it exists."""
    fault_log = pd.read_csv(DATA_DIR / "fault_log.csv").set_index("mission_id")
    missions = []

    for split, is_fault in [("test_healthy", False), ("test_fault", True)]:
        ids = pd.read_parquet(DATA_DIR / f"{split}.parquet", columns=["mission_id"])["mission_id"].unique()
        for mid in ids:
            entry = {"mission_id": mid, "split": split, "has_fault": is_fault}
            if is_fault and mid in fault_log.index:
                row = fault_log.loc[mid]
                entry.update({
                    "fault_type": row["fault_type"],
                    "fault_start_t": float(row["fault_start_t"]),
                    "failure_t": float(row["failure_t"]),
                })
            missions.append(entry)
    return missions


def load_mission_df(split, mission_id):
    df = pd.read_parquet(DATA_DIR / f"{split}.parquet")
    mission_df = df[df["mission_id"] == mission_id].set_index("t").sort_index()
    if mission_df.empty:
        raise KeyError(f"mission_id {mission_id!r} not found in {split}")
    return mission_df


def _per_model_percentiles(bundle, scores_list):
    """Each detector's raw score mapped to its percentile of the healthy
    validation distribution (same mapping the fuser averages)."""
    out = {}
    for name, scores in zip(bundle.model_names, scores_list):
        dist = bundle.fuser.val_scores[name]
        out[name] = np.searchsorted(dist, scores) / len(dist) * 100
    return out


def compute_mission_timeline(mission_df, bundle=None, hi_threshold=50, n_consecutive=8,
                             planned_mission_s=3600.0):
    """Runs the full digital-twin pipeline (healthy twin -> residuals ->
    IF/PCA/LSTM -> fusion -> Health Index -> alert -> RUL -> diagnosis ->
    Go/No-Go) over one mission's telemetry.

    mission_df: single-mission dataframe indexed by time `t` in seconds
    (see load_mission_df).

    Returns a list of dicts, one per sliding window: raw telemetry at the
    window's end, healthy-twin expected values, per-model anomaly
    percentiles, fused Health Index, alert flag, RUL estimate (seconds, or
    None if not yet estimable / health is flat-or-improving), fault
    diagnosis (None while healthy) and the mission advisor decision.
    """
    bundle = bundle or get_bundle()

    res, twin = compute_residuals(mission_df, bundle.cfg, return_twin=True)
    res = res.dropna()
    if res.empty:
        return []

    X_stats, times = bundle.pipeline.transform_to_stats(res, bundle.window_size, bundle.stride)
    X_seq, _ = bundle.pipeline.transform_to_sequences(res, bundle.window_size, bundle.stride)
    if len(X_stats) == 0:
        return []

    if_scores = bundle.if_model.score(X_stats)
    pca_scores = bundle.pca_model.score(X_stats)
    lstm_scores = bundle.lstm_model.score(X_seq)
    raw_scores = [if_scores, pca_scores, lstm_scores]

    fused = bundle.fuser.score(bundle.model_names, raw_scores)
    per_model = _per_model_percentiles(bundle, raw_scores)
    hi = compute_health_index(fused, p=bundle.p_calibrated)
    times = np.asarray(times)
    alerts = alert_logic(hi, times, threshold=hi_threshold, n_consecutive=n_consecutive)
    # A single noisy dip below 80 happens even in healthy windows -- gate RUL
    # on the same "sustained, not isolated" persistence principle alerts use,
    # just at a looser threshold/shorter run (an earlier "degrading" signal,
    # not yet an alert), so a brief blip doesn't produce a nonsense estimate.
    degrading = alert_logic(hi, times, threshold=80, n_consecutive=5)

    # Window-mean standardized residuals: the evidence the diagnosis engine
    # reads to decide *which* fault is present.
    z = pd.DataFrame(bundle.pipeline.scaler.transform(res), index=res.index, columns=res.columns)
    z_win = z.rolling(bundle.window_size, min_periods=1).mean()

    telemetry_cols = [c for c in TELEMETRY_COLS + ["ambient_c"] if c in mission_df.columns]
    has_phase = "phase" in mission_df.columns
    # Smoothed, for RUL extrapolation only -- raw per-window HI is noisy
    # enough that a linear fit over it is dominated by noise, not the
    # underlying trend. Alerting (above) deliberately uses the raw series;
    # its own persistence rule is the robustness mechanism there.
    hi_smooth = pd.Series(hi).rolling(20, min_periods=1).mean().values

    # Explainable AI: per-sensor attribution for every window the ensemble
    # flags (HI < 80); healthy-looking windows need no explanation.
    xai = explain(bundle, X_stats, X_seq, [i for i in range(len(hi)) if hi[i] < 80])

    # Bayesian health twin (particle filter) runs on the raw 1 Hz telemetry,
    # reporting at the same instants as the windows above.
    twin_est = HealthParticleFilter(bundle.cfg).run(mission_df, times, horizon_s=planned_mission_s)

    rows = []
    for i, t in enumerate(times):
        telem = mission_df.loc[t, telemetry_cols]
        tw = twin.loc[t]
        # A linear-trend RUL extrapolation is meaningless noise while HI is
        # still flat/nominal (tiny slope fluctuations swing the estimate
        # wildly) -- only report it once there's a sustained declining trend
        # to extrapolate. Even then this is a prototype point estimate with
        # no calibrated uncertainty band (see implementation plan Sec. 19).
        rul = None
        if degrading[i]:
            est = estimate_rul(hi_smooth[: i + 1], times[: i + 1], t, w=15, failure_threshold=50)
            rul = float(est) if np.isfinite(est) else None
        zrow = z_win.loc[t]
        row = {
            "t": float(t),
            "phase": str(mission_df.loc[t, "phase"]) if has_phase else None,
            **{k: float(v) for k, v in telem.items()},
            "exp": {
                "oil_press_bar": float(tw["oil_press_bar"]),
                "oil_temp_c": float(tw["oil_temp_c"]),
                "cht": float(np.mean([tw[f"cht_{n}"] for n in range(1, 5)])),
                "egt": float(np.mean([tw[f"egt_{n}"] for n in range(1, 5)])),
                "vib_rms_g": float(tw["vib_rms_g"]),
                "fuel_flow_lph": float(tw["fuel_flow_lph"]),
            },
            "z": {k.replace("_res", ""): round(float(v), 2) for k, v in zrow.items()},
            "scores": {name: round(float(per_model[name][i]), 1) for name in bundle.model_names},
            "fused": round(float(fused[i]), 1),
            "hi": float(hi[i]),
            "hi_smooth": float(hi_smooth[i]),
            "alert": bool(alerts[i]),
            # once a sustained alert has fired this flight, it stays latched
            # until a maintenance inspection clears it (not a self-reset)
            "alert_latched": bool(alerts[: i + 1].any()),
            "degrading": bool(degrading[i]),
            "rul_s": rul,
        }
        row["twin"] = twin_est.get(float(t))
        row["xai"] = xai.get(i)
        row["diagnosis"] = diagnose(zrow) if degrading[i] else None
        row["advisor"] = advise(row, bundle.cfg, planned_mission_s)
        rows.append(row)
    return rows
