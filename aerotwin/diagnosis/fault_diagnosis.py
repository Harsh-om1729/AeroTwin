"""Physics-informed fault diagnosis (fault isolation).

Anomaly detection (IF / PCA / LSTM-AE -> fused Health Index) answers *"is
something wrong?"*. This module answers *"what is wrong, and where?"* by
matching the pattern of standardized residuals (measured - healthy twin) to
the physical signature each fault mode produces in the engine model:

    fault mode            physical signature in residuals
    --------------------  ---------------------------------------------------
    lubrication           oil pressure drops below twin
    cooling_degradation   oil temp AND all four CHTs rise together
    injector_abnormality  one cylinder's EGT rises (lean/fuel maldistribution)
    misfire               one cylinder's EGT drops + vibration rises
    abnormal_vibration    vibration rises with no EGT asymmetry (bearing)

The signatures are written from engine physics, NOT fitted to the fault test
set, so diagnosis accuracy measured on that set is an honest held-out number.
"""
import numpy as np

FAULT_LABELS = {
    "lubrication": "Lubrication system degradation",
    "cooling_degradation": "Cooling system degradation",
    "injector_abnormality": "Fuel injector abnormality",
    "misfire": "Ignition misfire",
    "abnormal_vibration": "Abnormal vibration (bearing wear)",
}

FAULT_ACTIONS = {
    "lubrication": "Inspect oil pump, oil level, filter and pressure relief valve.",
    "cooling_degradation": "Inspect coolant level/radiator, cowling airflow and baffles.",
    "injector_abnormality": "Inspect fuel injector / carburetor on the flagged cylinder.",
    "misfire": "Inspect spark plugs and ignition leads on the flagged cylinder.",
    "abnormal_vibration": "Inspect crankshaft bearings, propeller balance and engine mounts.",
}

# Below this evidence level (in healthy-noise standard deviations, averaged
# over a 60 s window) no fault hypothesis is reported. Diagnosis only runs
# once the detectors have already confirmed sustained degradation, so this
# only has to separate the fault modes from each other, not from noise.
MIN_EVIDENCE = 2.0


def _z(zrow, name):
    return float(zrow.get(name, 0.0))


def diagnose(zrow):
    """zrow: mapping residual-column -> window-mean standardized residual
    (z-score w.r.t. healthy training residuals).

    Returns dict(fault, label, confidence, cylinder, scores, evidence, action)
    or None if no hypothesis has enough evidence.
    """
    oil_p = _z(zrow, "oil_press_bar_res")
    oil_t = _z(zrow, "oil_temp_c_res")
    vib = _z(zrow, "vib_rms_g_res")
    cht = np.array([_z(zrow, f"cht_{i}_res") for i in range(1, 5)])
    egt = np.array([_z(zrow, f"egt_{i}_res") for i in range(1, 5)])

    k_hot, k_cold = int(np.argmax(egt)), int(np.argmin(egt))
    egt_hot = egt[k_hot] - np.median(np.delete(egt, k_hot))
    egt_cold = np.median(np.delete(egt, k_cold)) - egt[k_cold]

    # A uniform CHT rise (all four cylinders) is what distinguishes cooling
    # loss from a single-cylinder problem -- use the coolest cylinder's rise.
    # Oil temp (slower thermal lag, tau ~120 s vs ~60 s for CHT) only
    # corroborates: a falling oil temp halves the cooling hypothesis.
    cooling = max(0.0, float(cht.min())) * (1.0 if oil_t >= 0 else 0.5)
    misfire = float(np.sqrt(max(0.0, egt_cold) * max(0.0, vib)))
    scores = {
        "lubrication": max(0.0, -oil_p),
        "cooling_degradation": cooling,
        "injector_abnormality": max(0.0, egt_hot),
        "misfire": misfire,
        # vibration that is explained by a misfiring cylinder is not a bearing fault
        "abnormal_vibration": max(0.0, vib) * float(np.exp(-max(0.0, egt_cold) / 3.0)),
    }

    best = max(scores, key=scores.get)
    if scores[best] < MIN_EVIDENCE:
        return None

    total = sum(scores.values())
    cylinder = None
    if best == "injector_abnormality":
        cylinder = k_hot + 1
    elif best == "misfire":
        cylinder = k_cold + 1

    evidence = {
        "lubrication": f"Oil pressure {oil_p:+.1f}σ vs healthy twin",
        "cooling_degradation": f"Oil temp {oil_t:+.1f}σ, CHT 1-4 {cht.min():+.1f}..{cht.max():+.1f}σ",
        "injector_abnormality": f"EGT cyl {k_hot + 1} {egt[k_hot]:+.1f}σ, other cylinders nominal",
        "misfire": f"EGT cyl {k_cold + 1} {egt[k_cold]:+.1f}σ with vibration {vib:+.1f}σ",
        "abnormal_vibration": f"Vibration {vib:+.1f}σ, no EGT asymmetry",
    }[best]

    return {
        "fault": best,
        "label": FAULT_LABELS[best],
        "confidence": round(scores[best] / total, 3) if total > 0 else 0.0,
        "cylinder": cylinder,
        "scores": {k: round(v, 2) for k, v in scores.items()},
        "evidence": evidence,
        "action": FAULT_ACTIONS[best] + (f" (cylinder {cylinder})" if cylinder else ""),
    }
