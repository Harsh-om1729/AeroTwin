"""CUSUM baseline, reality-gap engine and per-engine calibration."""
import numpy as np
import pytest

from aerotwin.evaluation.report import _persist
from aerotwin.inference.replay import CALIBRATION_COLS, estimate_calibration, get_bundle
from aerotwin.models.cusum import cusum_statistic
from aerotwin.simulator.generate_dataset import generate_mission_data
from aerotwin.simulator.variation import GapEngine


def test_cusum_is_quiet_on_noise_and_fast_on_a_shift():
    rng = np.random.default_rng(0)
    z = rng.normal(0, 1, (3600, 15))
    h = get_bundle().cusum_h
    assert cusum_statistic(z).max() < h
    z[1800:, 3] += 2.0  # a 2-sigma shift on one channel
    s = cusum_statistic(z)
    first = int(np.argmax(s > h))
    assert 1800 < first < 1800 + 30


def test_persistence_rule():
    assert _persist([1, 1, 0, 1, 1, 1, 1], 3) == [False, False, False, False, False, True, True]


def test_same_engine_seed_means_same_engine():
    cfg = get_bundle().cfg
    a, b = GapEngine(cfg, seed=1, gap=1.0, engine_seed=42), GapEngine(cfg, seed=2, gap=1.0, engine_seed=42)
    assert np.allclose(a.cht_off, b.cht_off) and a.tau == b.tau and a.bias == b.bias


def test_gap_zero_engine_has_no_offsets():
    e = GapEngine(get_bundle().cfg, seed=1, gap=0.0)
    assert np.allclose(e.cht_off, 0) and e.oil_gain == 1 and all(v == 0 for v in e.bias.values())


def test_calibration_removes_constant_offsets():
    cfg = get_bundle().cfg
    fly = lambda seed: generate_mission_data("T", "t", "standard", seed=seed, gap=1.0, engine_seed=999).set_index("t")
    cal = estimate_calibration(fly(1), cfg)
    assert set(cal) <= set(CALIBRATION_COLS)
    after = fly(2).copy()
    for c, off in cal.items():
        after[c] -= off
    resid = estimate_calibration(after, cfg)
    # constant offsets are largely removed (drift and gain errors remain)
    assert abs(resid["cht_1"]) < abs(cal["cht_1"]) or abs(cal["cht_1"]) < 0.5
    assert np.mean([abs(v) for v in resid.values()]) < np.mean([abs(v) for v in cal.values()])
