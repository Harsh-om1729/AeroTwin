"""Explainable-AI checks: the top-ranked sensor must be the one the injected
fault physically acts on, and healthy windows need no explanation."""
import pytest

from aerotwin.inference.simulate import run_scenario
from aerotwin.xai.attribution import CHANNELS, EXPECTED, top_channels


@pytest.mark.parametrize("fault", list(EXPECTED))
def test_top_sensor_matches_fault_physics(fault):
    r = run_scenario(fault, "moderate", onset_s=1200, profile="standard", seed=11)
    alert = next(x for x in r["timeline"] if x["alert"] and x["t"] >= 1200)
    assert top_channels(alert["xai"]["share"], 1)[0] in EXPECTED[fault]


def test_explanation_structure_and_bounds():
    r = run_scenario("lubrication", "moderate", onset_s=1200, profile="standard", seed=11)
    x = next(x for x in r["timeline"] if x["alert"])["xai"]
    assert set(x["share"]) <= set(CHANNELS)
    assert all(0 <= v <= 100 for v in x["share"].values())
    assert set(x["models"]) == {"IF", "PCA", "LSTM"}
    # removing the top sensor can only lower the fused anomaly percentile
    assert x["counterfactual"]["fused_without"] <= x["base"]["fused"]


def test_healthy_windows_are_not_explained():
    r = run_scenario(None, profile="standard", seed=1)
    healthy = [x for x in r["timeline"] if x["hi"] >= 80]
    assert healthy and all(x["xai"] is None for x in healthy)
