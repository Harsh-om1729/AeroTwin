import numpy as np
from aerotwin.simulator.atmosphere import isa, power_lapse

def step_temperature(T, T_target, tau, dt):
    """First-order thermal lag: sensors do not jump instantly."""
    return T + (T_target - T) * (dt / tau)

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
        T_amb_k, _, sigma = isa(alt_ft, ambient_c - 15.0) # approx ISA dev
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
            "alt_voltage_v": expected_alt_v
        }

    def step(self, rpm, throttle, alt_ft, ambient_c, dt=1.0, noise_scale=1.0):
        """Apply health degradation + lag + sensor noise -> one telemetry row."""
        exp = self.expected(rpm, throttle, alt_ft, ambient_c)
        
        # Apply health modifiers
        actual_oil_press = exp["oil_press_bar"] * self.health["oil"]
        
        # Reduce cooling efficiency -> higher target temp
        actual_oil_temp_target = exp["oil_temp_c"] * (2.0 - self.health["cooling"])
        actual_cht_target = np.array([exp["cht_c"]] * 4) * (2.0 - self.health["cooling"]) + self.cyl_bias
        
        # Injector health affects EGT
        actual_egt_target = np.array([exp["egt_c"]] * 4) * (2.0 - np.array(self.health["injector"])) + self.cyl_bias * 2
        
        # Misfire (ignition) affects vibration and EGT
        misfire_factor = 1.0 - np.mean(self.health["ignition"])
        actual_egt_target -= 100 * (1.0 - np.array(self.health["ignition"]))
        
        # Bearing health + misfire affects vibration
        actual_vib_rms = exp["vib_rms_g"] * (2.0 - self.health["bearing"]) + 5.0 * misfire_factor
        
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
