"""On-demand scenario simulation for the dashboard's Fault Injection Lab.

Generates a brand-new mission with the physics engine model (optionally with
an injected fault) and runs it through the trained pipeline. Nothing here is
precomputed: each request is a fresh, unseen mission.
"""
import numpy as np

from aerotwin.inference.replay import compute_mission_timeline, get_bundle
from aerotwin.simulator.fault_injection import FaultInjector, compute_failure_t
from aerotwin.simulator.generate_dataset import generate_mission_data

# Default degradation rates used to build the fault test set (generate_dataset)
BASE_RATES = {
    "lubrication": 0.001,
    "cooling_degradation": 0.002,
    "injector_abnormality": 0.003,
    "misfire": 0.005,
    "abnormal_vibration": 0.002,
}
SEVERITY_MULT = {"mild": 0.5, "moderate": 1.0, "severe": 2.0}
PROFILES = ["standard", "hot_weather", "high_altitude", "rapid_throttle"]


def run_scenario(fault_type=None, severity="moderate", onset_s=1200, profile="standard", seed=None):
    if profile not in PROFILES:
        raise ValueError(f"profile must be one of {PROFILES}")
    if fault_type and fault_type not in BASE_RATES:
        raise ValueError(f"fault_type must be one of {list(BASE_RATES)} or none")
    if severity not in SEVERITY_MULT:
        raise ValueError(f"severity must be one of {list(SEVERITY_MULT)}")

    seed = int(np.random.randint(0, 1_000_000)) if seed is None else int(seed)
    np.random.seed(seed)  # rapid_throttle profile jitter uses the global RNG
    onset_s = int(np.clip(onset_s, 300, 3000))

    injector, truth = None, {"fault_type": None}
    if fault_type:
        rate = BASE_RATES[fault_type] * SEVERITY_MULT[severity]
        injector = FaultInjector(fault_type, onset_s, rate)
        truth = {
            "fault_type": fault_type,
            "severity": severity,
            "fault_start_t": float(onset_s),
            "failure_t": float(compute_failure_t(fault_type, onset_s, rate)),
            "rate": float(rate),
        }

    df = generate_mission_data("SIM", f"sim_{seed}", profile, seed=seed, fault_injector=injector)
    timeline = compute_mission_timeline(df.set_index("t").sort_index(), get_bundle())

    first_alert = next((r for r in timeline if r["alert"]), None)
    result = {"first_alert_t": first_alert["t"] if first_alert else None}
    if first_alert and first_alert["diagnosis"]:
        result["diagnosed_as"] = first_alert["diagnosis"]["fault"]
        result["cylinder"] = first_alert["diagnosis"]["cylinder"]
    if fault_type and first_alert:
        result["detection_delay_s"] = first_alert["t"] - onset_s
        result["lead_time_s"] = truth["failure_t"] - first_alert["t"]

    # Bayesian health twin: first confident (P(degraded) > 0.95) detection
    twin_det = next((r for r in timeline if r["twin"]["p_degraded"] > 0.95), None)
    result["twin_detect_t"] = twin_det["t"] if twin_det else None
    if twin_det:
        result["twin_diagnosis"] = twin_det["twin"]["map"]
        if fault_type:
            result["twin_delay_s"] = twin_det["t"] - onset_s
            result["twin_lead_time_s"] = truth["failure_t"] - twin_det["t"]

    return {"seed": seed, "profile": profile, "truth": truth, "result": result, "timeline": timeline}
