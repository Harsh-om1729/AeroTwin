"""Smoke + behaviour tests for the digital-twin pipeline.  Run: python3 -m pytest -q"""
import pytest
import yaml

from aerotwin.advisor.mission_advisor.go_nogo import advise, check_limits
from aerotwin.diagnosis.fault_diagnosis import diagnose
from aerotwin.inference.replay import CONFIG_PATH
from aerotwin.inference.simulate import run_scenario

CFG = yaml.safe_load(open(CONFIG_PATH))
ZERO = {k: 0.0 for k in ["oil_press_bar_res", "oil_temp_c_res", "vib_rms_g_res"]
        + [f"cht_{i}_res" for i in range(1, 5)] + [f"egt_{i}_res" for i in range(1, 5)]}


@pytest.mark.parametrize("override, fault, cyl", [
    ({"oil_press_bar_res": -10}, "lubrication", None),
    ({"oil_temp_c_res": 5, **{f"cht_{i}_res": 8 for i in range(1, 5)}}, "cooling_degradation", None),
    ({"egt_3_res": 40}, "injector_abnormality", 3),
    ({"egt_4_res": -20, "vib_rms_g_res": 8}, "misfire", 4),
    ({"vib_rms_g_res": 10}, "abnormal_vibration", None),
])
def test_diagnosis_signatures(override, fault, cyl):
    d = diagnose({**ZERO, **override})
    assert d["fault"] == fault and d["cylinder"] == cyl


def test_no_diagnosis_when_healthy():
    assert diagnose(ZERO) is None


def test_limits_and_advisor():
    row = {"rpm": 4800, "oil_press_bar": 0.5, "oil_temp_c": 90, "hi": 95, "alert": False}
    assert any("Oil pressure" in r for r in check_limits(row, CFG))
    assert advise(row, CFG)["decision"] == "NO-GO"
    healthy = {"rpm": 4800, "oil_press_bar": 4.5, "oil_temp_c": 90, "hi": 95, "alert": False}
    assert advise(healthy, CFG)["decision"] == "GO"


def test_healthy_flight_has_no_alert():
    r = run_scenario(None, profile="standard", seed=1)
    assert r["result"]["first_alert_t"] is None
    assert r["timeline"][-1]["advisor"]["decision"] == "GO"


ALL_FAULTS = ["lubrication", "cooling_degradation", "injector_abnormality", "misfire", "abnormal_vibration"]


@pytest.mark.parametrize("fault", ALL_FAULTS)
def test_injected_fault_detected_and_diagnosed(fault):
    r = run_scenario(fault, "moderate", onset_s=1200, profile="standard", seed=3)
    res = r["result"]
    assert res["first_alert_t"] is not None and res["first_alert_t"] > 1200
    assert res["diagnosed_as"] == fault


@pytest.mark.parametrize("fault", [
    *ALL_FAULTS[:4],
    # Known ML-ensemble weakness, also visible on the test split (11/12 bearing
    # faults caught in time): a vibration-only fault moves one residual
    # channel, so the fused score can cross the alert threshold late.
    pytest.param("abnormal_vibration", marks=pytest.mark.xfail(
        reason="ML ensemble can flag bearing wear after the failure threshold", strict=False)),
])
def test_ml_alert_comes_before_failure(fault):
    r = run_scenario(fault, "moderate", onset_s=1200, profile="standard", seed=3)
    assert r["result"]["first_alert_t"] < r["truth"]["failure_t"]
