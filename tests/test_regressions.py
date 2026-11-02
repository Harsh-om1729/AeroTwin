"""Regression tests for bugs found in the project audit."""
import json

import numpy as np
import pandas as pd
import pytest

from aerotwin.evaluation.detection_rate import evaluate_detections, first_new_alarm_index
from aerotwin.evaluation.report import _clean
from aerotwin.evaluation.stats import clopper_pearson
from aerotwin.features.windowing import FeaturePipeline, create_windows
from aerotwin.health.rul import estimate_rul


def test_first_new_alarm_ignores_alarm_already_on_at_onset():
    t = [0, 10, 20, 30, 40]
    assert first_new_alarm_index([0, 1, 1, 1, 1], t, onset=20, failure=100) is None
    assert first_new_alarm_index([0, 1, 0, 1, 1], t, onset=20, failure=100) == 3


def test_first_new_alarm_ignores_alarm_after_failure():
    t = [0, 10, 20, 30]
    assert first_new_alarm_index([0, 0, 0, 1], t, onset=5, failure=30) is None


def test_detection_requires_new_alarm_in_window():
    log = pd.DataFrame([{"mission_id": "m", "fault_type": "misfire", "fault_start_t": 20, "failure_t": 60}])
    stuck = {"m": [(0, False), (10, True), (20, True), (30, True)]}  # on before onset
    assert not evaluate_detections(stuck, log)["detected"].iloc[0]
    fresh = {"m": [(0, False), (10, False), (20, False), (30, True)]}
    row = evaluate_detections(fresh, log).iloc[0]
    assert row["detected"] and row["lead_time"] == 30


def test_create_windows_short_input_has_same_shape_as_normal_input():
    df = pd.DataFrame(np.zeros((10, 3)))
    windows, times = create_windows(df, window_size=60, stride=10)
    assert windows.shape == (0, 60, 3) and len(times) == 0


def _fitted(df):
    p = FeaturePipeline()
    p.fit(pd.DataFrame(np.random.default_rng(0).normal(size=(100, 3))))
    return p


def test_transform_to_stats_short_mission_returns_empty():
    df = pd.DataFrame(np.zeros((10, 3)))
    stats, times = _fitted(df).transform_to_stats(df)
    assert len(stats) == 0 and len(times) == 0


def test_rul_zero_when_already_failed_and_flat():
    t = np.arange(20.0)
    assert estimate_rul(np.full(20, 30.0), t, 19.0, failure_threshold=50) == 0.0


def test_rul_ignores_nan_samples():
    t = np.arange(20.0)
    hi = 100 - 2.0 * t
    hi[5] = np.nan
    assert estimate_rul(hi, t, 19.0, w=20) == pytest.approx(6.0, abs=0.01)


def test_clean_makes_strict_json():
    out = _clean({"a": float("nan"), "b": [np.float64("inf"), 1.0], "c": {"d": np.nan}})
    assert out == {"a": None, "b": [None, 1.0], "c": {"d": None}}
    json.dumps(out, allow_nan=False)


def test_clopper_pearson_empty_sample_is_nan_not_error():
    lo, hi = clopper_pearson(0, 0)
    assert np.isnan(lo) and np.isnan(hi)


def test_particle_filter_rates_stay_inside_bounds():
    from aerotwin.simulator.engine_model import EngineModel  # noqa: F401
    from aerotwin.inference.replay import get_bundle
    from aerotwin.twin.particle_filter import HealthParticleFilter

    pf = HealthParticleFilter(get_bundle().cfg, n_per_mode=20, seed=1, rate_walk=1.0)
    pf._init_state(np.array([3.0, 80.0] + [100.0] * 4 + [600.0] * 4 + [1.0]))
    for _ in range(200):
        pf._propagate()
    lo, hi = pf.rate_bounds
    assert pf.logr.min() >= lo - 1e-12 and pf.logr.max() <= hi + 1e-12


def test_env_loader_handles_export_and_inline_comments(tmp_path, monkeypatch):
    from aerotwin.copilot.llm import load_env_file
    f = tmp_path / ".env"
    f.write_text('export COPILOT_T1=abc # note\nCOPILOT_T2="x # y"\n')
    for k in ("COPILOT_T1", "COPILOT_T2"):
        monkeypatch.delenv(k, raising=False)
    load_env_file(f)
    import os
    assert os.environ.pop("COPILOT_T1") == "abc"
    assert os.environ.pop("COPILOT_T2") == "x # y"


def test_redline_breach_keeps_next_mission_no_go_after_recovery():
    from aerotwin.advisor.mission_advisor.go_nogo import advise
    from aerotwin.inference.replay import get_bundle
    cfg = get_bundle().cfg
    row = {"rpm": 4800, "oil_press_bar": 4.0, "oil_temp_c": 90, "hi": 95, "alert": False, "alert_latched": False,
           "degrading": False, "twin": None, "rul_s": None}
    assert advise(row, cfg)["decision"] == "GO"
    late = advise({**row, "limit_breach": {"t": 400.0, "reason": "CHT cyl 1 140 °C above limit 135 °C"}}, cfg)
    assert late["decision"] == "NO-GO" and "T+06:40" in late["reasons"][0]


def test_load_mission_returns_only_that_mission():
    from aerotwin.inference.replay import load_mission_df
    df = load_mission_df("test_healthy", "test_8_5")
    assert set(df["mission_id"]) == {"test_8_5"} and len(df) == 3600 and df.index.is_monotonic_increasing


def test_scenario_seeds_do_not_follow_from_the_previous_seed(monkeypatch):
    from aerotwin.inference import simulate
    seen = []
    def fake(airframe, mission, profile, seed, **kw):
        seen.append(seed)
        raise ValueError("stop")
    monkeypatch.setattr(simulate, "generate_mission_data", fake)
    for _ in range(2):
        np.random.seed(5)
        with pytest.raises(ValueError):
            simulate.run_scenario()
    assert seen[0] != seen[1]


def test_offline_intent_does_not_match_rul_inside_words():
    from aerotwin.copilot.offline import detect_intent
    assert detect_intent("Is the rule based check right?") != "rul"
    assert detect_intent("What is the RUL of AT-104?") == "rul"
