import pandas as pd
import numpy as np
from aerotwin.simulator.engine_model import EngineModel


def _simulate_healthy_twin(mission_df, cfg):
    """Steps a perfectly-healthy EngineModel through the same rpm/throttle/
    altitude/ambient trajectory as `mission_df` (one mission, time-sorted).
    This gives a *lagged* healthy baseline (thermal lag matches what a real
    healthy engine would read at a climb/cruise/descent transition) instead
    of an instantaneous steady-state target -- comparing against the
    instantaneous target makes every throttle/altitude change look like a
    huge anomaly even in a healthy engine, which swamps real fault signal.
    """
    twin = EngineModel(cfg, seed=0)  # default health = perfectly healthy
    rows = [
        twin.step(
            rpm=r.rpm, throttle=r.throttle_pct, alt_ft=r.altitude_ft,
            ambient_c=r.ambient_c, dt=1.0, noise_scale=0.0,
        )
        for r in mission_df.itertuples()
    ]
    return pd.DataFrame(rows, index=mission_df.index)


def compute_residuals(df, cfg, return_twin=False):
    """
    Computes the residual = measured - expected(healthy twin) for each sensor
    column. Adds derived spread features (egt_spread, cht_spread).

    If `df` has a "mission_id" column, the healthy twin is simulated
    separately per mission (thermal-lag state must not carry over from one
    mission's landing into the next mission's taxi).

    With return_twin=True, also returns the healthy-twin expected telemetry
    (same index), so callers can show measured-vs-expected side by side.
    """
    groups = (
        [g.sort_index() for _, g in df.groupby("mission_id", sort=False)]
        if "mission_id" in df.columns else [df]
    )

    res_parts, twin_parts = [], []
    for g in groups:
        twin = _simulate_healthy_twin(g, cfg)
        twin_parts.append(twin)
        res = pd.DataFrame(index=g.index)

        for col in ["oil_press_bar", "oil_temp_c", "fuel_flow_lph", "vib_rms_g", "alt_voltage_v"]:
            if col in g.columns and col in twin.columns:
                res[col + "_res"] = g[col] - twin[col]

        for i in range(1, 5):
            if f"cht_{i}" in g.columns:
                res[f"cht_{i}_res"] = g[f"cht_{i}"] - twin[f"cht_{i}"]
            if f"egt_{i}" in g.columns:
                res[f"egt_{i}_res"] = g[f"egt_{i}"] - twin[f"egt_{i}"]

        cht_cols = [c for c in g.columns if c.startswith("cht_")]
        egt_cols = [c for c in g.columns if c.startswith("egt_")]
        if cht_cols:
            res["cht_spread"] = g[cht_cols].max(axis=1) - g[cht_cols].min(axis=1)
        if egt_cols:
            res["egt_spread"] = g[egt_cols].max(axis=1) - g[egt_cols].min(axis=1)

        res_parts.append(res)

    if return_twin:
        return pd.concat(res_parts), pd.concat(twin_parts)
    return pd.concat(res_parts)
