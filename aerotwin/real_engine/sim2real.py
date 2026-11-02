"""From the simulator's world to real flights.

The physics twin describes a Rotax 912, not a Cessna 172's engine, so its
equations do not apply here. A healthy baseline is LEARNED instead: from
after-maintenance flights, predict each sensor from what the pilot and the
atmosphere are doing. The residual then plays the same role as
measured - physics twin, and the rest of the AeroTwin stack is reused as is.
There is no throttle channel in this dataset; fuel flow stands in for it.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from aerotwin.real_engine.feature_extraction import COVARIATES, SENSORS

MAX_FIT_ROWS = 400_000


class HealthyBaseline:
    def __init__(self, seed=0):
        self.seed = seed
        self.models = {}

    def fit(self, blocks):
        d = blocks if len(blocks) <= MAX_FIT_ROWS else blocks.sample(MAX_FIT_ROWS, random_state=self.seed)
        X = d[COVARIATES].to_numpy()
        for s in SENSORS:
            self.models[s] = HistGradientBoostingRegressor(max_iter=200, random_state=self.seed).fit(X, d[s].to_numpy())
        return self

    def predict(self, blocks):
        X = blocks[COVARIATES].to_numpy()
        return pd.DataFrame({s: m.predict(X) for s, m in self.models.items()}, index=blocks.index)

    def residuals(self, blocks):
        """Residual per sensor, plus cylinder spreads as in the Rotax pipeline."""
        pred = self.predict(blocks)
        res = pd.DataFrame({f"{s}_res": blocks[s] - pred[s] for s in SENSORS}, index=blocks.index)
        for kind in ("cht", "egt"):
            cols = [f"{kind}_{i}" for i in range(1, 5)]
            res[f"{kind}_spread"] = blocks[cols].max(axis=1) - blocks[cols].min(axis=1)
        return res


def windows(res, blocks, pipeline, size, stride):
    """Window statistics and sequences, per contiguous segment of each flight.
    Returns (stats, sequences, flight id of each window)."""
    stats, seqs, owners = [], [], []
    keys = [blocks["flight"].to_numpy(), blocks["segment"].to_numpy()]
    for (flight, _), idx in res.groupby(keys, sort=False).groups.items():
        part = res.loc[idx]
        if len(part) < size:
            continue
        st, _ = pipeline.transform_to_stats(part, size, stride)
        sq, _ = pipeline.transform_to_sequences(part, size, stride)
        stats.append(st)
        seqs.append(sq)
        owners.append(np.full(len(st), flight))
    if not stats:
        return np.empty((0, 3 * res.shape[1])), np.empty((0, size, res.shape[1])), np.empty(0)
    return np.concatenate(stats), np.concatenate(seqs), np.concatenate(owners)
