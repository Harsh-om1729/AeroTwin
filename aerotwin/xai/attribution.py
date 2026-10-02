"""Explainable AI for the unsupervised ensemble: which sensors made the
models flag this window?

Method: sensor-level counterfactual occlusion. For one flagged window, each
of the 15 residual channels is in turn replaced by its healthy baseline,
everything else is left as measured, and all three detectors are re-scored.
The drop in a model's anomaly score is that sensor's contribution (see
explain() for the exact, saturation-free formula):

    contribution(c) = score(window) - score(window with channel c made healthy)

"If the oil-pressure residual had been normal, the fused anomaly percentile
would have fallen from 97 to 22" is a direct, falsifiable statement about the
model's actual decision, and it works identically for Isolation Forest, PCA,
the LSTM autoencoder and the percentile fusion.

Why not SHAP: TreeSHAP covers only the Isolation Forest, and only at the level
of the 45 window statistics (mean/std/slope per channel), not sensors; the
LSTM and the fusion would need slow sampling-based approximations. Occlusion
at sensor level is exact for "what would the model have said without this
sensor's deviation", costs one batched re-score, and is checked against
ground truth in aerotwin.evaluation.report (explanation hit rate).

Healthy baseline: window statistics -> their mean over the healthy training
windows (the fitted PCA's mean_); sequences -> 0 (standardised residuals of a
healthy engine have zero mean).
"""
import numpy as np

CHANNELS = [
    "oil_press_bar", "oil_temp_c", "fuel_flow_lph", "vib_rms_g", "alt_voltage_v",
    "cht_1", "egt_1", "cht_2", "egt_2", "cht_3", "egt_3", "cht_4", "egt_4",
    "cht_spread", "egt_spread",
]
LABELS = {
    "oil_press_bar": "Oil pressure", "oil_temp_c": "Oil temp", "fuel_flow_lph": "Fuel flow",
    "vib_rms_g": "Vibration", "alt_voltage_v": "Alternator V",
    "cht_1": "CHT 1", "cht_2": "CHT 2", "cht_3": "CHT 3", "cht_4": "CHT 4",
    "egt_1": "EGT 1", "egt_2": "EGT 2", "egt_3": "EGT 3", "egt_4": "EGT 4",
    "cht_spread": "CHT spread", "egt_spread": "EGT spread",
}
# Physically correct channels for each simulated fault: used only to CHECK
# explanations against ground truth, never by the attribution itself.
EXPECTED = {
    "lubrication": {"oil_press_bar"},
    "cooling_degradation": {"oil_temp_c", "cht_1", "cht_2", "cht_3", "cht_4"},
    "injector_abnormality": {"egt_1", "egt_spread"},
    "misfire": {"egt_2", "egt_spread", "vib_rms_g"},
    "abnormal_vibration": {"vib_rms_g"},
}


def _percentiles(bundle, raw):
    out = []
    for name, scores in zip(bundle.model_names, raw):
        dist = bundle.fuser.val_scores[name]
        out.append(np.searchsorted(dist, scores) / len(dist) * 100)
    return out  # list of arrays, one per model


def explain(bundle, X_stats, X_seq, idxs):
    """Attributions for the windows `idxs` of one mission.

    X_stats: (N, 3F) window statistics [means | stds | slopes]
    X_seq:   (N, W, F) standardised residual sequences

    Attribution is computed on each model's RAW score (Isolation-Forest depth,
    PCA SPE, LSTM reconstruction error), not its percentile: percentiles
    saturate at 100, so when a fault moves several sensors at once, removing
    any single one would still leave 100 and every contribution would read 0.
    For model m and channel c:

        share_m(c) = (raw_m - raw_m[c made healthy]) / (raw_m - healthy median of raw_m)

    i.e. the fraction of the model's excess anomaly evidence that channel c
    explains. The ensemble share is the mean over the three models, mirroring
    how the fusion averages them.

    Returns {i: {"base": percentiles, "share": {channel: % of evidence},
                 "models": {model: {channel: %}} (top 4), "counterfactual":
                 {"channel", "fused_without"}}}.
    """
    idxs = list(idxs)
    if not idxs:
        return {}
    F = X_seq.shape[2]
    assert F == len(CHANNELS), "residual channel layout changed; update CHANNELS"
    baseline_stats = bundle.pca_model.model.mean_  # healthy training mean of each statistic
    healthy_med = [float(np.median(bundle.fuser.val_scores[m])) for m in bundle.model_names]

    # Batch: for every window, the original (k = 0) plus one copy per occluded channel
    n_var = F + 1
    S = np.repeat(X_stats[idxs], n_var, axis=0)
    Q = np.repeat(X_seq[idxs], n_var, axis=0)
    for w in range(len(idxs)):
        for c in range(F):
            r = w * n_var + 1 + c
            cols = [c, c + F, c + 2 * F]
            S[r, cols] = baseline_stats[cols]
            Q[r, :, c] = 0.0

    raw = [bundle.if_model.score(S), bundle.pca_model.score(S), bundle.lstm_model.score(Q)]
    perc = _percentiles(bundle, raw)
    fused = np.mean(perc, axis=0)

    out = {}
    for w, i in enumerate(idxs):
        b = w * n_var
        rows = slice(b + 1, b + n_var)
        shares = {}
        for m, r, med in zip(bundle.model_names, raw, healthy_med):
            excess = r[b] - med
            sh = np.clip((r[b] - r[rows]) / excess, 0, 1) if excess > 1e-12 else np.zeros(F)
            shares[m] = sh
        ens = np.mean([shares[m] for m in bundle.model_names], axis=0)
        top = int(np.argmax(ens))
        out[i] = {
            "base": {"fused": round(float(fused[b]), 1),
                     **{m: round(float(p[b]), 1) for m, p in zip(bundle.model_names, perc)}},
            "share": {ch: round(100 * float(v), 1) for ch, v in zip(CHANNELS, ens) if v >= 0.005},
            "models": {m: dict(sorted(((ch, round(100 * float(v), 1)) for ch, v in zip(CHANNELS, shares[m]) if v >= 0.005),
                                      key=lambda kv: -kv[1])[:4])
                       for m in bundle.model_names},
            "counterfactual": {"channel": CHANNELS[top], "fused_without": round(float(fused[b + 1 + top]), 1)},
        }
    return out


def top_channels(contrib, k=3):
    """Channels sorted by contribution (largest first), zero contributions dropped."""
    return [c for c, v in sorted(contrib.items(), key=lambda kv: -kv[1]) if v > 0][:k]
