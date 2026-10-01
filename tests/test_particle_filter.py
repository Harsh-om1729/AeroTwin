"""Flagship particle-filter health twin: behaviour tests on fresh flights."""
import numpy as np
import pytest

from aerotwin.simulator.fault_injection import FaultInjector, compute_failure_t, degrade
from aerotwin.simulator.generate_dataset import generate_mission_data, load_config
from aerotwin.twin.particle_filter import HealthParticleFilter

CFG = load_config()


def _run(fault, rate, onset=1200, seed=31337):
    np.random.seed(seed)
    fi = FaultInjector(fault, onset, rate) if fault else None
    df = generate_mission_data("T", "t", "standard", seed=seed, fault_injector=fi).set_index("t")
    return HealthParticleFilter(CFG).run(df, df.index[59::10])


def test_healthy_flight_stays_healthy():
    res = _run(None, None)
    assert max(s["p_degraded"] for s in res.values()) < 0.5


@pytest.mark.parametrize("fault, rate, cyl", [
    ("lubrication", 0.001, None),
    ("cooling_degradation", 0.002, None),
    ("injector_abnormality", 0.003, 1),
    ("misfire", 0.005, 2),
    ("abnormal_vibration", 0.002, None),
])
def test_fault_detected_diagnosed_and_tracked(fault, rate, cyl):
    onset = 1200
    res = _run(fault, rate, onset)
    fail = compute_failure_t(fault, onset, rate)
    det = next(t for t, s in sorted(res.items()) if s["p_degraded"] > 0.95)
    assert onset <= det < fail                       # after onset, before failure
    s = res[det]
    assert s["map"]["fault"] == fault and s["map"]["cylinder"] == cyl
    # hidden health tracked within 0.05 a little after detection
    t = min(det + 30, max(res))
    shape = "lin" if fault == "misfire" else "exp"
    assert abs(res[t]["health"]["p50"] - degrade(t, onset, rate, shape)) < 0.05
