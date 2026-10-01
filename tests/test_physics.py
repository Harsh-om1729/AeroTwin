"""Guards for the P0 physics fixes (ISA temperature, unit-correct faults)."""
import numpy as np
import pytest
import yaml

from aerotwin.inference.replay import CONFIG_PATH
from aerotwin.simulator.atmosphere import isa_from_oat
from aerotwin.simulator.engine_model import EngineModel, apply_health

CFG = yaml.safe_load(open(CONFIG_PATH))


@pytest.mark.parametrize("alt_ft, oat_c", [(0, 15), (5000, 5), (15000, -25), (10000, 20)])
def test_isa_uses_the_measured_oat(alt_ft, oat_c):
    T, _, _ = isa_from_oat(alt_ft, oat_c)
    assert T - 273.15 == pytest.approx(oat_c)


def test_standard_day_density_ratio():
    # ISA standard day at 5,000 ft: sigma ~= 0.862
    _, _, sigma = isa_from_oat(5000, 15 - 0.0019812 * 5000)
    assert sigma == pytest.approx(0.862, abs=0.002)


def test_density_falls_with_altitude():
    sig = [isa_from_oat(h, 15 - 0.0019812 * h)[2] for h in (0, 5000, 10000, 15000)]
    assert all(a > b for a, b in zip(sig, sig[1:]))


def _exp(amb=5.0):
    return EngineModel(CFG, 0).expected(4800, 75, 5000, amb)


def test_health_one_changes_nothing():
    e = _exp()
    t = apply_health(e, 1.0, 1.0, np.ones(4), np.ones(4), 1.0)
    assert t["oil_press_bar"] == pytest.approx(e["oil_press_bar"])
    assert t["oil_temp_c"] == pytest.approx(e["oil_temp_c"])
    assert np.allclose(t["cht_c"], e["cht_c"]) and np.allclose(t["egt_c"], e["egt_c"])
    assert t["vib_rms_g"] == pytest.approx(e["vib_rms_g"])


def test_cooling_effect_acts_on_rise_above_ambient():
    """Unit-independent: the cooling fault scales the temperature RISE, so the
    extra degrees do not depend on how far ambient is from 0 C."""
    extra = []
    for amb in (-20.0, 30.0):
        e = _exp(amb)
        healthy = apply_health(e, 1, 1.0, np.ones(4), np.ones(4), 1)["cht_c"][0]
        faulty = apply_health(e, 1, 0.6, np.ones(4), np.ones(4), 1)["cht_c"][0]
        extra.append((faulty - healthy) / (healthy - amb))
    assert extra[0] == pytest.approx(extra[1]) == pytest.approx(0.4)


def test_lean_cylinder_egt_is_bounded():
    e = _exp()
    t = apply_health(e, 1, 1, np.array([0.0, 1, 1, 1]), np.ones(4), 1)
    assert t["egt_c"][0] - e["egt_c"] == pytest.approx(150.0)
    assert t["egt_c"][0] < CFG["egt"]["max"] + 50


def test_vectorised_particles_match_scalar():
    e = _exp()
    h = np.array([1.0, 0.8, 0.5])
    vec = apply_health(e, np.ones(3), h, np.ones((3, 4)), np.ones((3, 4)), np.ones(3))
    for i, hi in enumerate(h):
        sc = apply_health(e, 1.0, hi, np.ones(4), np.ones(4), 1.0)
        assert np.allclose(vec["cht_c"][i], sc["cht_c"]) and vec["oil_temp_c"][i] == pytest.approx(sc["oil_temp_c"])
