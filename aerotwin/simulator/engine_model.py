import numpy as np
from aerotwin.simulator.atmosphere import isa_from_oat, power_lapse

def step_temperature(T, T_target, tau, dt):
    """First-order thermal lag: sensors do not jump instantly."""
    return T + (T_target - T) * (dt / tau)

# Peak EGT rise of a fully lean cylinder over its neighbours (degC). A lean
# mixture raises EGT towards peak, then EGT falls again, so the effect is
# bounded rather than proportional to EGT itself.
LEAN_EGT_RISE_C = 150.0
MISFIRE_EGT_DROP_C = 100.0
MISFIRE_VIB_G = 5.0


def apply_health(exp, oil, cooling, injector, ignition, bearing):
    """Healthy expected values (from EngineModel.expected) -> degraded
    targets. Shared by the data generator and the particle filter so both use
    exactly one definition of each fault's physics.

    Broadcasts: scalars for one engine, or arrays of shape (N,) / (N, 4) for
    N particles. Temperature effects act on the *rise above ambient* (a
    loss of cooling conductance h raises the rise by ~1/h; 2 - h is its
    first-order expansion around h = 1), so they are independent of the
    temperature unit. At health 1 every effect is exactly zero.
    """
    amb = exp["ambient_c"]
    cool_gain = 2.0 - np.asarray(cooling, dtype=float)
    injector = np.asarray(injector, dtype=float)
    ignition = np.asarray(ignition, dtype=float)
    cht_rise = (exp["cht_c"] - amb) * cool_gain
    egt = (exp["egt_c"]
           + LEAN_EGT_RISE_C * (1.0 - injector)
           - MISFIRE_EGT_DROP_C * (1.0 - ignition))
    return {
        "oil_press_bar": exp["oil_press_bar"] * np.asarray(oil, dtype=float),
        "oil_temp_c": amb + (exp["oil_temp_c"] - amb) * cool_gain,
        "cht_c": amb + np.asarray(cht_rise)[..., None] * np.ones(4),  # same for all 4 cylinders
        "egt_c": egt,
        "vib_rms_g": exp["vib_rms_g"] * (2.0 - np.asarray(bearing, dtype=float))
                     + MISFIRE_VIB_G * (1.0 - ignition.mean(axis=-1)),
    }


class EngineModel:
    def __init__(self, cfg, seed, health=None):
        self.rng = np.random.default_rng(seed)
        self.cfg = cfg
        # health parameters in [0,1]; 1 = perfect. Faults reduce these.
        self.health = health or {"oil": 1.0, "cooling": 1.0,
                                 "injector": [1.0]*4, "ignition": [1.0]*4,
                                 "bearing": 1.0}
        # No per-cylinder manufacturing bias: a prototype healthy-twin
        # baseline can't know another engine's random bias draw, so making
        # this random here would just show up as permanent "phantom residual"
        # on every mission, drowning out real fault signal.
        self.cyl_bias = np.zeros(4)
        
        # State variables
        self.oil_temp = 20.0
        self.cht = np.array([20.0]*4)
        self.egt = np.array([20.0]*4)
        
    def expected(self, rpm, throttle, alt_ft, ambient_c):
        """Physics twin: expected healthy values. Used both to generate data
        and to compute residuals later."""
        # ambient_c is the outside air temperature at this altitude, so it
        # already includes the lapse rate (see isa_from_oat).
        T_amb_k, _, sigma = isa_from_oat(alt_ft, ambient_c)
        power_ratio = throttle / 100.0 * power_lapse(sigma)
        
        # Oil pressure
        # Base oil pressure depends on RPM, reduces slightly if oil temp is high (viscosity)
        rpm_norm = rpm / 5800.0 # max rpm
        expected_oil_press = 1.5 + 4.0 * rpm_norm
        
        # Oil Temp Target
        expected_oil_temp_target = T_amb_k - 273.15 + 40.0 + 60.0 * power_ratio
        
        # CHT Target
        expected_cht_target = T_amb_k - 273.15 + 50.0 + 80.0 * power_ratio
        
        # EGT Target
        expected_egt_target = T_amb_k - 273.15 + 200.0 + 600.0 * power_ratio
        
        # Fuel Flow
        expected_fuel_flow = 5.0 + 20.0 * power_ratio
        
        # Vibration
        expected_vib_rms = 0.5 + 2.5 * rpm_norm
        
        # Alternator
        expected_alt_v = np.where(rpm > 1500, 13.8, 12.0)
        
        return {
            "oil_press_bar": expected_oil_press,
            "oil_temp_c": expected_oil_temp_target,
            "cht_c": expected_cht_target,
            "egt_c": expected_egt_target,
            "fuel_flow_lph": expected_fuel_flow,
            "vib_rms_g": expected_vib_rms,
            "alt_voltage_v": expected_alt_v,
            "ambient_c": T_amb_k - 273.15,
        }

    def step(self, rpm, throttle, alt_ft, ambient_c, dt=1.0, noise_scale=1.0):
        """Apply health degradation + lag + sensor noise -> one telemetry row."""
        exp = self.expected(rpm, throttle, alt_ft, ambient_c)
        
        h = self.health
        t = apply_health(exp, h["oil"], h["cooling"], np.array(h["injector"]),
                         np.array(h["ignition"]), h["bearing"])
        actual_oil_press = t["oil_press_bar"]
        actual_oil_temp_target = t["oil_temp_c"]
        actual_cht_target = t["cht_c"] + self.cyl_bias
        actual_egt_target = t["egt_c"] + self.cyl_bias * 2
        actual_vib_rms = t["vib_rms_g"]

        # Step temperatures (lag)
        self.oil_temp = step_temperature(self.oil_temp, actual_oil_temp_target, tau=120.0, dt=dt)
        self.cht = step_temperature(self.cht, actual_cht_target, tau=60.0, dt=dt)
        self.egt = step_temperature(self.egt, actual_egt_target, tau=5.0, dt=dt)
        
        # Add noise
        noise = lambda scale: self.rng.normal(0, scale) * noise_scale
        
        row = {
            "rpm": rpm + noise(10),
            "throttle_pct": throttle,
            "altitude_ft": alt_ft,
            "ambient_c": ambient_c,
            "oil_press_bar": max(0.0, actual_oil_press + noise(0.1)),
            "oil_temp_c": self.oil_temp + noise(1.0),
            "fuel_flow_lph": exp["fuel_flow_lph"] + noise(0.5),
            "vib_rms_g": max(0.0, actual_vib_rms + noise(0.1)),
            "alt_voltage_v": exp["alt_voltage_v"] + noise(0.2)
        }
        for i in range(4):
            row[f"cht_{i+1}"] = self.cht[i] + noise(1.0)
            row[f"egt_{i+1}"] = self.egt[i] + noise(2.0)
            
        return row
