import numpy as np

def degrade(t, t0, rate, shape="exp"):
    """Returns health multiplier in (0,1]; 1 before onset."""
    if t < t0:
        return 1.0
    x = t - t0
    return float(np.exp(-rate * x)) if shape == "exp" else max(0.0, 1 - rate * x)

# Health value at which each fault mode is considered a functional failure
# (engine would realistically need to shut down / abort mission). These are
# still engineering judgment calls, not a direct inversion of the Rotax 912
# S/ULS redlines in configs/engine_rotax912.yaml (oil 0.8-7 bar, oil temp
# max 130 C, CHT max 135 C, EGT max 880 C) -- they only need to be internally
# consistent so ground-truth labels are well-defined for evaluation.
CRITICAL_HEALTH = {
    "lubrication": 0.30,          # oil pressure/lubrication effectiveness
    "cooling_degradation": 0.40,  # cooling capacity
    "injector_abnormality": 0.40, # single-cylinder injector health
    "misfire": 0.50,              # ignition health (linear degrade)
    "abnormal_vibration": 0.30,   # bearing health
    "overheating_trend": 0.40,    # combined cooling+oil, each at rate/2
}

def compute_failure_t(fault_type, fault_start_t, severity_rate, critical_health=None):
    """Analytically inverts `degrade()` to find the time t at which the
    relevant health channel for `fault_type` first crosses its critical
    (functional-failure) value. This is the ground-truth `failure_t` paired
    with `fault_start_t` in the fault log.
    """
    c = CRITICAL_HEALTH[fault_type] if critical_health is None else critical_health
    rate = severity_rate / 2.0 if fault_type == "overheating_trend" else severity_rate
    shape = "lin" if fault_type == "misfire" else "exp"

    if shape == "lin":
        # health = max(0, 1 - rate*(t - t0)) = c  =>  t = t0 + (1-c)/rate
        return fault_start_t + (1.0 - c) / rate
    # health = exp(-rate*(t - t0)) = c  =>  t = t0 + ln(1/c)/rate
    return fault_start_t + np.log(1.0 / c) / rate

class FaultInjector:
    def __init__(self, fault_type, fault_start_t, severity_rate):
        self.fault_type = fault_type
        self.fault_start_t = fault_start_t
        self.rate = severity_rate
        
    def get_health(self, t):
        health = {
            "oil": 1.0, 
            "cooling": 1.0,
            "injector": [1.0]*4, 
            "ignition": [1.0]*4,
            "bearing": 1.0
        }
        
        if self.fault_type == "lubrication":
            health["oil"] = degrade(t, self.fault_start_t, self.rate)
        elif self.fault_type == "cooling_degradation":
            health["cooling"] = degrade(t, self.fault_start_t, self.rate)
        elif self.fault_type == "injector_abnormality":
            health["injector"][0] = degrade(t, self.fault_start_t, self.rate)
        elif self.fault_type == "misfire":
            health["ignition"][1] = degrade(t, self.fault_start_t, self.rate, shape="lin")
        elif self.fault_type == "abnormal_vibration":
            health["bearing"] = degrade(t, self.fault_start_t, self.rate)
        elif self.fault_type == "overheating_trend":
            health["cooling"] = degrade(t, self.fault_start_t, self.rate/2)
            health["oil"] = degrade(t, self.fault_start_t, self.rate/2)
            
        return health
