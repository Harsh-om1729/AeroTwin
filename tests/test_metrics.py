"""Guards for the evaluation fixes: false alarms are counted as events."""
import pandas as pd
import pytest

from aerotwin.evaluation.false_alarms import count_false_alarms
from aerotwin.evaluation.stats import clopper_pearson, poisson_rate_ci

LOG = pd.DataFrame({"mission_id": ["f1"], "fault_start_t": [100.0]})


def _p(flags, dt=10.0):
    return [(i * dt, f) for i, f in enumerate(flags)]


def test_one_long_alarm_is_one_event():
    preds = {"h1": _p([0, 1, 1, 1, 1, 0, 0])}
    r = count_false_alarms(preds, LOG, {"h1": 3600})
    assert r["events"] == 1 and r["healthy_hours"] == pytest.approx(1.0)


def test_separate_alarms_count_separately():
    preds = {"h1": _p([1, 0, 1, 1, 0, 1])}
    assert count_false_alarms(preds, LOG, {"h1": 3600})["events"] == 3


def test_alerts_after_fault_onset_are_not_false_alarms():
    # fault starts at t=100: windows at t>=100 are true detections
    preds = {"f1": _p([0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1])}
    r = count_false_alarms(preds, LOG, {"f1": 3600})
    assert r["events"] == 1 and r["healthy_hours"] == pytest.approx(100 / 3600)


def test_exact_intervals():
    lo, hi = clopper_pearson(60, 60)
    assert hi == 1.0 and lo == pytest.approx(0.9404, abs=1e-3)
    lo, hi = poisson_rate_ci(0, 80.0)
    assert lo == 0.0 and hi == pytest.approx(3.689 / 80.0, rel=1e-3)
