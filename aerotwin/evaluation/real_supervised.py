"""Supervised maintenance detection on real NGAFID flights (Cessna 172).

    python3 -m aerotwin.evaluation.real_supervised          # development fold only
    python3 -m aerotwin.evaluation.real_supervised --test   # adds "supervised" to cache/real_results.json

Unlike real_report, these models DO learn from the before/after labels. Folds:

    fold 0     fits the healthy baseline (real_report), so unused here: its
               residuals are in-sample and would look unrealistically clean
    folds 1-2  train
    fold 3     development: choose the model and threshold
    fold 4     test. real_report already used it once, so its scores here are
               a second look at that fold, and the report says so.

Feature sets answer a question, not just a score: if a model loses most of its
skill without oil pressure, then the "signal" is the oil-pressure shift, which a
repair visit that changes the oil would also produce.
"""
import json
import sys

import joblib
import numpy as np
import pandas as pd
import torch
from torch import nn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

from aerotwin.evaluation.real_report import MODEL_PATH, RESULTS_PATH, _decision, event_bootstrap, load_blocks

OIL_P = "oil_press_bar_res"
FEATURE_SETS = {"all sensors": lambda c: True, "without oil pressure": lambda c: c != OIL_P,
                "oil pressure only": lambda c: c == OIL_P}
TRAIN_FOLDS, DEV_FOLD, TEST_FOLD = (1, 2), 3, 4
SEQ_LEN = 256             # 10 s blocks, about 43 min
CHOICES = ["Gradient boosting", "1D CNN"]


def flight_table(res, flights):
    """Per-flight summary of each residual channel."""
    g = res.groupby(np.asarray(flights), sort=False)
    t = pd.concat({"mean": g.mean(), "std": g.std(), "q10": g.quantile(0.1), "q90": g.quantile(0.9)}, axis=1)
    t.columns = [f"{c}|{s}" for s, c in t.columns]
    return t.fillna(0.0)


def sequences(res, flights, mean, std, keep):
    """Last SEQ_LEN blocks of each flight, standardised and zero-padded in front."""
    Z = ((res.to_numpy()[:, keep] - mean[keep]) / std[keep]).astype("float32")
    out, order = [], []
    for fl, idx in pd.Series(np.arange(len(res))).groupby(np.asarray(flights), sort=False).groups.items():
        x = np.zeros((SEQ_LEN, len(keep)), dtype="float32")
        z = Z[idx][-SEQ_LEN:]
        x[-len(z):] = z
        out.append(x)
        order.append(fl)
    return np.stack(out).transpose(0, 2, 1), np.array(order)


class Cnn(nn.Module):
    def __init__(self, n_ch):
        super().__init__()
        layers, ch = [], n_ch
        for out in (32, 64, 64):
            layers += [nn.Conv1d(ch, out, 7, stride=2, padding=3), nn.BatchNorm1d(out), nn.ReLU()]
            ch = out
        self.body = nn.Sequential(*layers, nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Dropout(0.3), nn.Linear(ch, 1))

    def forward(self, x):
        return self.body(x).squeeze(1)


def fit_cnn(X, y, epochs=12, seed=0):
    torch.manual_seed(seed)
    net = Cnn(X.shape[1])
    opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=1e-2)
    data = torch.utils.data.TensorDataset(torch.from_numpy(X), torch.from_numpy(y.astype("float32")))
    for _ in range(epochs):
        net.train()
        for xb, yb in torch.utils.data.DataLoader(data, batch_size=64, shuffle=True):
            opt.zero_grad()
            nn.functional.binary_cross_entropy_with_logits(net(xb), yb).backward()
            opt.step()
    return net.eval()


def cnn_scores(net, X):
    with torch.no_grad():
        return np.concatenate([net(torch.from_numpy(X[i:i + 256])).numpy() for i in range(0, len(X), 256)])


def fit_gbm(X, y):
    return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200, l2_regularization=1.0,
                                          random_state=0).fit(X, y)


def summary(y, s, groups, threshold=None):
    d = _decision(s, y, threshold)
    return {"auc": float(roc_auc_score(y, s)), "ci95": event_bootstrap(y, s, groups), **d}


def run(test=False):
    blocks, header, _ = load_blocks()
    bundle = joblib.load(MODEL_PATH)
    use = header[header["fold"].isin([*TRAIN_FOLDS, DEV_FOLD] + ([TEST_FOLD] if test else []))].set_index("flight")
    d = blocks[blocks["flight"].isin(use.index)]
    res = bundle["baseline"].residuals(d)
    fl = d["flight"].to_numpy()
    table = flight_table(res, fl)
    meta = use.loc[table.index]
    split = lambda folds: meta["fold"].isin(folds).to_numpy()
    tr, dev, te = split(TRAIN_FOLDS), split([DEV_FOLD]), split([TEST_FOLD])
    y, groups = meta["before"].to_numpy(), meta["event_group"].to_numpy()

    mask = np.isin(fl, table.index[tr])
    mean, std = res[mask].mean().to_numpy(), res[mask].std().to_numpy()
    results = {}
    for name, want in FEATURE_SETS.items():
        cols = [c for c in table.columns if want(c.split("|")[0])]
        gbm = fit_gbm(table.loc[tr, cols].to_numpy(), y[tr])
        keep = [i for i, c in enumerate(res.columns) if want(c)]
        X, order = sequences(res, fl, mean, std, keep)
        pos = pd.Series(np.arange(len(order)), index=order).loc[table.index].to_numpy()
        X = X[pos]
        net = fit_cnn(X[tr], y[tr])
        scored = {"Gradient boosting": lambda m: gbm.predict_proba(table.loc[m, cols].to_numpy())[:, 1],
                  "1D CNN": lambda m: cnn_scores(net, X[m])}
        for model, score in scored.items():
            key = f"{model} · {name}"
            r = {"model": model, "features": name, "dev": summary(y[dev], score(dev), groups[dev])}
            if test:
                r["test"] = summary(y[te], score(te), groups[te], r["dev"]["threshold"])
            results[key] = r
            print(f"{key:48s} dev AUC {r['dev']['auc']:.3f} bal {r['dev']['balanced_accuracy']:.3f}"
                  + (f" | test AUC {r['test']['auc']:.3f} bal {r['test']['balanced_accuracy']:.3f}" if test else ""), flush=True)
    return {"train_flights": int(tr.sum()), "dev_flights": int(dev.sum()), "test_flights": int(te.sum()),
            "test_fold_note": "Second use of this fold: real_report evaluated it first.", "results": list(results.values())}


if __name__ == "__main__":
    test = "--test" in sys.argv
    out = run(test)
    if test:
        r = json.loads(RESULTS_PATH.read_text())
        r["supervised"] = out
        RESULTS_PATH.write_text(json.dumps(r, allow_nan=False))
