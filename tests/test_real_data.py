"""NGAFID loader and evaluation helpers, on small fixtures (no download needed)."""
import numpy as np
import pandas as pd
import pytest

from aerotwin.evaluation.real_report import event_bootstrap
from aerotwin.real_engine.feature_extraction import COVARIATES, SENSORS, infer_repair_groups, load_header, resample_flight, to_si
from aerotwin.real_engine.sim2real import HealthyBaseline


def raw_flight(n=1500, flight=7):
    t = np.arange(n)
    d = {"Master Index": flight, "timestep": t, "E1 RPM": 2400.0, "E1 FFlow": 10.0, "E1 OilT": 212.0, "E1 OilP": 100.0,
         "OAT": 15.0, "IAS": 100.0, "VSpd": 0.0, "AltMSL": 3000.0}
    d |= {f"E1 CHT{i}": 212.0 for i in range(1, 5)} | {f"E1 EGT{i}": 1292.0 for i in range(1, 5)}
    return pd.DataFrame(d).sample(frac=1, random_state=0)  # the dataset is not in time order


def test_units_are_converted():
    s = to_si(raw_flight()).iloc[0]
    assert s["oil_temp_c"] == pytest.approx(100.0) and s["cht_1"] == pytest.approx(100.0)
    assert s["egt_4"] == pytest.approx(700.0) and s["oil_press_bar"] == pytest.approx(6.89476)
    assert s["fuel_flow_lph"] == pytest.approx(37.8541) and s["ambient_c"] == 15.0


def test_flight_is_put_in_time_order_and_warmup_removed():
    b = resample_flight(to_si(raw_flight()))
    assert b["block"].is_monotonic_increasing and b["t_since_start"].min() >= 300
    assert not b[SENSORS + COVARIATES].isna().any().any()


def test_gap_starts_a_new_segment():
    f = to_si(raw_flight(2000))
    f.loc[(f["t"] > 900) & (f["t"] < 1000), "ias_kt"] = 0.0  # back on the ground
    assert resample_flight(f)["segment"].nunique() == 2


def test_flight_missing_a_cylinder_sensor_is_rejected():
    f = to_si(raw_flight())
    f["cht_3"] = np.nan
    assert resample_flight(f) is None


def test_short_flight_is_rejected():
    assert resample_flight(to_si(raw_flight(500))) is None


def test_repair_groups_split_on_issue_change_and_new_before():
    h = pd.DataFrame({"Master Index": [1, 2, 3, 4, 5, 6], "label": list("aaaaab"),
                      "before_after": ["before", "same", "after", "before", "after", "before"]})
    assert infer_repair_groups(h).tolist() == [1, 1, 1, 2, 2, 3]


def test_repair_spanning_two_folds_is_dropped(tmp_path):
    d, a = tmp_path / "2days" / "2days", tmp_path / "all_flights" / "all_flights"
    d.mkdir(parents=True), a.mkdir(parents=True)
    pd.DataFrame({"Master Index": [1, 2, 3, 4], "label": list("aaaa"), "before_after": ["before", "after", "before", "after"]}
                 ).to_csv(a / "flight_header.csv", index=False)
    pd.DataFrame({"Master Index": [1, 2, 3, 4], "before_after": [1, 0, 1, 0], "fold": [0, 1, 3, 3], "hierarchy": ["oil", None, "oil", "oil"],
                  "label": list("aaaa")}).to_csv(d / "flight_header.csv", index=False)
    h = load_header(tmp_path)
    assert h["flight"].tolist() == [3, 4] and (h.groupby("event_group")["fold"].nunique() == 1).all()


def test_bootstrap_ci_contains_the_auc_of_a_noisy_score():
    rng = np.random.default_rng(0)
    groups = np.repeat(np.arange(100), 4)
    y = np.tile([0, 1, 0, 1], 100)
    s = y + rng.normal(0, 1, 400)
    lo, hi = event_bootstrap(y, s, groups, n=200)
    assert lo < 0.76 < hi and hi - lo < 0.2


def test_baseline_residual_is_near_zero_when_the_sensor_follows_the_covariates():
    rng = np.random.default_rng(0)
    n = 3000
    d = pd.DataFrame({c: rng.normal(0, 1, n) for c in COVARIATES})
    for s in SENSORS:
        d[s] = 5 * d["rpm"] + 2 * d["ambient_c"]
    res = HealthyBaseline().fit(d).residuals(d)
    assert res["cht_1_res"].abs().mean() < 0.5 and "egt_spread" in res


def test_decision_threshold_from_dev_is_reused_unchanged():
    from aerotwin.evaluation.real_report import _decision
    y = np.array([0] * 80 + [1] * 20)
    s = np.r_[np.linspace(0, 1, 80), np.linspace(0.8, 1.8, 20)]
    dev = _decision(s, y)
    assert dev["balanced_accuracy"] > 0.85 and dev["recall_before"] > 0.8  # not the "flag nothing" answer
    assert _decision(s + 5, y, dev["threshold"])["threshold"] == dev["threshold"]


def test_real_cache_does_not_mark_the_rotax_results_stale():
    from aerotwin.evaluation.real_report import BLOCKS_PATH, DATA_DIR
    assert BLOCKS_PATH.parent != DATA_DIR  # report.inputs_mtime only watches data/*.parquet


def test_flight_table_and_sequences_keep_one_row_per_flight():
    from aerotwin.evaluation.real_supervised import SEQ_LEN, flight_table, sequences
    res = pd.DataFrame({"a_res": np.arange(6.0), "b_res": np.ones(6)})
    fl = np.array([7, 7, 7, 9, 9, 9])
    assert list(flight_table(res, fl).index) == [7, 9]
    X, order = sequences(res, fl, np.zeros(2), np.ones(2), [0])
    assert X.shape == (2, 1, SEQ_LEN) and order.tolist() == [7, 9]
    assert X[1, 0, -1] == 5.0 and X[1, 0, 0] == 0.0  # padded in front, latest block last


def _archive(tmp_path, all_rows, bench_rows):
    d, a = tmp_path / "2days" / "2days", tmp_path / "all_flights" / "all_flights"
    d.mkdir(parents=True), a.mkdir(parents=True)
    pd.DataFrame(all_rows).to_csv(a / "flight_header.csv", index=False)
    pd.DataFrame(bench_rows).to_csv(d / "flight_header.csv", index=False)


def test_full_archive_flights_inherit_their_repair_fold(tmp_path):
    from aerotwin.real_engine.feature_extraction import FIT_ONLY, load_header_all
    # repair A: flights 1-4 (benchmark has 2, 3 in fold 3); repair B: 5-6, no benchmark flight
    _archive(tmp_path,
             {"Master Index": [1, 2, 3, 4, 5, 6], "label": list("aaaabb"), "hierarchy": [None] * 6,
              "before_after": ["before", "before", "after", "after", "before", "after"],
              "date_diff": [-9, -1, 1, 20, -3, 2]},
             {"Master Index": [2, 3], "before_after": [1, 0], "fold": [3, 3], "hierarchy": [None, None], "label": list("aa")})
    h = load_header_all(tmp_path).set_index("flight")
    assert h.loc[[1, 2, 3, 4], "fold"].tolist() == [3, 3, 3, 3]
    assert h.loc[[5, 6], "fold"].tolist() == [FIT_ONLY, FIT_ONLY]
    assert h.loc[[2, 3], "in_benchmark"].all() and not h.loc[[1, 4], "in_benchmark"].any()


def test_full_archive_drops_repairs_spanning_folds(tmp_path):
    from aerotwin.real_engine.feature_extraction import load_header_all
    _archive(tmp_path,
             {"Master Index": [1, 2, 3], "label": list("aaa"), "hierarchy": [None] * 3,
              "before_after": ["before", "before", "after"], "date_diff": [-5, -1, 1]},
             {"Master Index": [2, 3], "before_after": [1, 0], "fold": [3, 4], "hierarchy": [None, None], "label": list("aa")})
    assert load_header_all(tmp_path).empty


def test_fit_only_flights_never_reach_the_evaluation_folds():
    from aerotwin.evaluation.real_leadtime import fit_header
    from aerotwin.real_engine.feature_extraction import FIT_ONLY
    h = pd.DataFrame({"flight": [1, 2, 3], "fold": [FIT_ONLY, 3, 4], "before": [0, 0, 1]})
    assert fit_header(h)["fold"].tolist() == [0, 3, 4]


def test_trend_test_finds_a_score_that_rises_towards_the_repair():
    from aerotwin.evaluation.real_leadtime import SCORES, trend_test
    rng = np.random.default_rng(0)
    rows = []
    for g in range(30):
        for day in range(-10, 0):
            rows.append({"event_group": g, "before_after": "before", "date_diff": day,
                         **{s: day + rng.normal(0, 1) for s in SCORES}})
    t = trend_test(pd.DataFrame(rows))
    assert all(t[s]["mean_rho"] > 0.5 and t[s]["wilcoxon_p"] < 0.01 for s in SCORES)


def test_every_day_falls_in_exactly_one_lead_time_bin():
    from aerotwin.evaluation.real_leadtime import BINS, _bin
    for day in range(-108, 71):
        assert sum(lo <= day <= hi for lo, hi, _ in BINS) == 1 and _bin(day)
