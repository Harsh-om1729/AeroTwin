"""Reality-gap engine: a "true" engine that differs from the digital twin.

The healthy twin (features/residuals.py) and the particle filter use the
nominal EngineModel. With gap = 0 the data come from exactly that model, which
is why the matched-simulation results are an upper bound. GapEngine draws a
specific engine + sensor set whose behaviour departs from the nominal model
by an amount controlled by one knob, `gap` in [0, 1]:

    engine-to-engine variation   per-cylinder CHT/EGT offsets, oil-pump gain,
                                 baseline vibration level
    model mismatch               heat-rejection gain (temperature rise above
                                 ambient), thermal time constants
    sensor imperfections         constant calibration bias, slow random-walk
                                 drift, AR(1) coloured noise

At gap = 1 the magnitudes are deliberately realistic-to-pessimistic for an
uncalibrated twin: CHT offsets of ~5 C, EGT ~15 C, time constants +-30%,
drift reaching ~1 sigma over an hour. The values are engineering judgement,
chosen before running the study, and recorded here so the study can be
repeated or argued with.

The faults themselves (fault_injection / apply_health) are unchanged, so a
gap study isolates the effect of the twin not matching the engine.
"""
import numpy as np

from aerotwin.simulator.engine_model import EngineModel, apply_health, step_temperature

SENSOR_SIGMA = {
    "rpm": 10.0, "oil_press_bar": 0.1, "oil_temp_c": 1.0, "fuel_flow_lph": 0.5,
    "vib_rms_g": 0.1, "alt_voltage_v": 0.2,
    **{f"cht_{i}": 1.0 for i in range(1, 5)}, **{f"egt_{i}": 2.0 for i in range(1, 5)},
}

# Magnitudes at gap = 1 (standard deviations of the per-engine draws unless noted)
AT_FULL_GAP = {
    "cht_offset_c": 5.0,
    "egt_offset_c": 15.0,
    "oil_gain": 0.05,            # oil-pump pressure gain, relative
    "vib_gain": 0.10,            # baseline vibration level, relative
    "heat_gain": 0.06,           # temperature rise above ambient, relative
    "tau_spread": 0.30,          # thermal time constants, uniform +-30%
    "bias_sigmas": 1.5,          # constant sensor bias, in sensor-noise sigmas
    "drift_sigmas_per_hour": 1.0,
    "ar_phi": 0.7,               # AR(1) coefficient of the sensor noise
}


class GapEngine(EngineModel):
    def __init__(self, cfg, seed, gap, health=None, engine_seed=None):
        """seed drives the sensor noise of this flight; engine_seed identifies
        the physical engine + sensor installation (its offsets, gains, bias),
        so two flights of the same engine share engine_seed."""
        super().__init__(cfg, seed, health)
        self.gap = float(gap)
        g, A = self.gap, AT_FULL_GAP
        r = np.random.default_rng((seed if engine_seed is None else engine_seed) + 7_919_000)
        self.cht_off = r.normal(0, A["cht_offset_c"] * g, 4)
        self.egt_off = r.normal(0, A["egt_offset_c"] * g, 4)
        self.oil_gain = 1 + r.normal(0, A["oil_gain"] * g)
        self.vib_gain = 1 + r.normal(0, A["vib_gain"] * g)
        self.heat_gain = 1 + r.normal(0, A["heat_gain"] * g)
        self.tau = {k: v * (1 + r.uniform(-1, 1) * A["tau_spread"] * g) for k, v in
                    {"oil": 120.0, "cht": 60.0, "egt": 5.0}.items()}
        self.bias = {k: r.normal(0, A["bias_sigmas"] * s * g) for k, s in SENSOR_SIGMA.items()}
        self.drift_step = {k: A["drift_sigmas_per_hour"] * s * g / 60.0 for k, s in SENSOR_SIGMA.items()}
        self.drift = {k: 0.0 for k in SENSOR_SIGMA}
        self.phi = A["ar_phi"] * g
        self.ar = {k: 0.0 for k in SENSOR_SIGMA}

    def _sensor(self, key, true_value, noise_scale):
        """Measured = true + bias + drift + AR(1) noise with the same marginal
        variance as the nominal white noise."""
        s = SENSOR_SIGMA[key]
        self.drift[key] += self.rng.normal(0, self.drift_step[key])
        e = self.phi * self.ar[key] + np.sqrt(1 - self.phi ** 2) * self.rng.normal(0, s)
        self.ar[key] = e
        return true_value + (self.bias[key] + self.drift[key] + e) * noise_scale

    def step(self, rpm, throttle, alt_ft, ambient_c, dt=1.0, noise_scale=1.0):
        exp = dict(self.expected(rpm, throttle, alt_ft, ambient_c))
        amb = exp["ambient_c"]
        exp["oil_temp_c"] = amb + (exp["oil_temp_c"] - amb) * self.heat_gain
        exp["cht_c"] = amb + (exp["cht_c"] - amb) * self.heat_gain
        exp["oil_press_bar"] = exp["oil_press_bar"] * self.oil_gain
        exp["vib_rms_g"] = exp["vib_rms_g"] * self.vib_gain

        h = self.health
        t = apply_health(exp, h["oil"], h["cooling"], np.array(h["injector"]), np.array(h["ignition"]), h["bearing"])
        self.oil_temp = step_temperature(self.oil_temp, t["oil_temp_c"], tau=self.tau["oil"], dt=dt)
        self.cht = step_temperature(self.cht, t["cht_c"] + self.cht_off, tau=self.tau["cht"], dt=dt)
        self.egt = step_temperature(self.egt, t["egt_c"] + self.egt_off, tau=self.tau["egt"], dt=dt)

        row = {
            "rpm": self._sensor("rpm", rpm, noise_scale),
            "throttle_pct": throttle,
            "altitude_ft": alt_ft,
            "ambient_c": ambient_c,
            "oil_press_bar": max(0.0, self._sensor("oil_press_bar", t["oil_press_bar"], noise_scale)),
            "oil_temp_c": self._sensor("oil_temp_c", self.oil_temp, noise_scale),
            "fuel_flow_lph": self._sensor("fuel_flow_lph", exp["fuel_flow_lph"], noise_scale),
            "vib_rms_g": max(0.0, self._sensor("vib_rms_g", t["vib_rms_g"], noise_scale)),
            "alt_voltage_v": self._sensor("alt_voltage_v", exp["alt_voltage_v"], noise_scale),
        }
        for i in range(4):
            row[f"cht_{i + 1}"] = self._sensor(f"cht_{i + 1}", self.cht[i], noise_scale)
            row[f"egt_{i + 1}"] = self._sensor(f"egt_{i + 1}", self.egt[i], noise_scale)
        return row
