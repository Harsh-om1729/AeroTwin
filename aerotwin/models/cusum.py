"""CUSUM baseline: the textbook sequential detector for a mean shift.

With an exact physics twin, a healthy residual is independent Gaussian noise
of known variance, and Page's CUSUM is the optimal detector for a persistent
shift in its mean (it minimises worst-case detection delay for a given
false-alarm rate). That makes it the right baseline for the ML ensemble and
the particle filter: if they cannot beat CUSUM on this data, the extra
machinery has not earned its place.

Per standardised residual channel j (z_j ~ N(0, 1) when healthy):

    S+_j(t) = max(0, S+_j(t-1) + z_j(t) - k)     (upward shift)
    S-_j(t) = max(0, S-_j(t-1) - z_j(t) - k)     (downward shift)

statistic(t) = max over channels and sides. k = 0.5 tunes it for shifts of
about 1 sigma. The alarm threshold h is calibrated on healthy validation
flights only (see calibrate()).
"""
import json

import numpy as np

K = 0.5


def cusum_statistic(z, k=K):
    """z: (T, C) standardised residuals at 1 Hz -> (T,) max CUSUM statistic."""
    z = np.asarray(z, dtype=float)
    sp = np.zeros(z.shape[1])
    sn = np.zeros(z.shape[1])
    out = np.empty(len(z))
    for t in range(len(z)):
        sp = np.maximum(0.0, sp + z[t] - k)
        sn = np.maximum(0.0, sn - z[t] - k)
        out[t] = max(sp.max(), sn.max())
    return out


def calibrate(statistics, margin=1.1):
    """Threshold h from healthy validation flights: the largest statistic
    seen on any of them, times a small margin, i.e. zero false alarms on the
    calibration flights, the same "healthy data only" rule the Health Index
    calibration follows."""
    return float(max(np.max(s) for s in statistics) * margin)


def load_or_calibrate(path, compute_statistics):
    """Cached threshold in models/cusum.json; computed once from healthy
    validation data if absent."""
    if path.exists():
        return json.load(open(path))["h"]
    h = calibrate(compute_statistics())
    json.dump({"k": K, "h": h, "calibrated_on": "val_healthy"}, open(path, "w"), indent=2)
    return h
