"""Bayesian health twin: infers the engine's *hidden* degradation state from
sensor data and predicts remaining useful life as a probability distribution.

Method -- a bank of hypothesis-specific particle filters with Bayesian model
selection (a multiple-model / jump-Markov particle filter):

  * One hypothesis per physical fault mode and location (11 in total):
    lubrication, cooling, injector on cylinder 1-4, misfire on cylinder 1-4,
    bearing wear. Each runs its own particle filter.
  * Particle state: hidden health h in [0, 1] of that hypothesis' component,
    degradation rate r (health/s), an "onset has happened" flag (the fault
    onset time is unknown -- each healthy particle may switch on at any
    second), and the particle's own thermal state (oil temp, 4x CHT, 4x EGT),
    because temperatures lag behind health changes.
  * Prediction: every particle is pushed through the physics engine model
    (same equations as aerotwin.simulator.engine_model) to predict all 11
    health-sensitive sensors.
  * Update: Gaussian sensor likelihood re-weights particles inside each
    filter; each filter's predictive likelihood updates the posterior
    probability of its hypothesis (Bayes' rule over hypotheses), with a small
    mixing term so no hypothesis ever becomes impossible.
  * Prognosis: each degraded particle is extrapolated at its own rate to the
    functional-failure health of its fault mode (CRITICAL_HEALTH); the
    weighted spread of crossing times is the RUL distribution.

What the filter does NOT know (deliberate model mismatch): the true
degradation law (exponential vs linear), its rate, or when it starts. It uses
a generic locally-linear decline with a slowly drifting rate.
"""
import numpy as np

from aerotwin.simulator.engine_model import EngineModel
from aerotwin.simulator.fault_injection import CRITICAL_HEALTH

MODES = (
    [("lubrication", None), ("cooling_degradation", None)]
    + [("injector_abnormality", k) for k in range(1, 5)]
    + [("misfire", k) for k in range(1, 5)]
    + [("abnormal_vibration", None)]
)
MODE_KEYS = [f"{f}:{c}" if c else f for f, c in MODES]

# Sensor noise std (matches the sensor model) for the 11 observed channels:
# oil_press, oil_temp, cht1-4, egt1-4, vib
SENSOR_SIGMA = np.array([0.1, 1.0] + [1.0] * 4 + [2.0] * 4 + [0.1])
OBS_COLS = ["oil_press_bar", "oil_temp_c"] + [f"cht_{i}" for i in range(1, 5)] \
    + [f"egt_{i}" for i in range(1, 5)] + ["vib_rms_g"]

# A component is called "degraded" once its health falls below this.
DEGRADED_H = 0.97
RUL_QUANTILES = [5, 10, 25, 50, 75, 90, 95]


def _weighted_quantiles(x, w, qs):
    order = np.argsort(x)
    x, w = x[order], w[order]
    cw = np.cumsum(w)
    cw /= cw[-1]
    return [float(x[min(np.searchsorted(cw, q / 100.0), len(x) - 1)]) for q in qs]


class HealthParticleFilter:
    # Defaults chosen by aerotwin.twin.tune on freshly simulated flights only
    # (never the test set): best-calibrated 90% RUL interval (91% empirical
    # coverage), health-tracking MAE 0.005, zero false alarms.
    def __init__(self, cfg, n_per_mode=120, seed=0, sigma_inflate=1.5, p_onset=0.005,
                 rate_bounds=(2e-4, 3e-2), rate_walk=0.05, health_walk=1e-3, mix=1e-3):
        self.cfg = cfg
        self.rng = np.random.default_rng(seed)
        self.M, self.n = len(MODES), n_per_mode
        self.N = self.M * self.n
        self.sigma = SENSOR_SIGMA * sigma_inflate
        self.p_onset, self.rate_bounds = p_onset, np.log(rate_bounds)
        self.rate_walk, self.health_walk, self.mix = rate_walk, health_walk, mix
        self.physics = EngineModel(cfg, seed=0)  # used only for its expected() physics

        mode_of = np.repeat(np.arange(self.M), self.n)
        ftype = np.array([MODES[m][0] for m in mode_of])
        cyl = np.array([MODES[m][1] or 0 for m in mode_of])
        self.is_lub = ftype == "lubrication"
        self.is_cool = ftype == "cooling_degradation"
        self.is_bear = ftype == "abnormal_vibration"
        self.inj_onehot = np.zeros((self.N, 4))
        self.ign_onehot = np.zeros((self.N, 4))
        for i in range(self.N):
            if ftype[i] == "injector_abnormality":
                self.inj_onehot[i, cyl[i] - 1] = 1
            elif ftype[i] == "misfire":
                self.ign_onehot[i, cyl[i] - 1] = 1
        self.crit = np.array([CRITICAL_HEALTH[MODES[m][0]] for m in mode_of])

    # ---------------------------------------------------------------------
    def _init_state(self, y0):
        N = self.N
        self.h = np.ones(N)
        self.logr = np.full(N, self.rate_bounds[0])
        self.active = np.zeros(N, dtype=bool)
        self.oil_t = np.full(N, y0[1])
        self.cht = np.tile(y0[2:6], (N, 1))
        self.egt = np.tile(y0[6:10], (N, 1))
        self.logw = np.full((self.M, self.n), -np.log(self.n))
        self.log_pi = np.full(self.M, -np.log(self.M))

    def _propagate(self):
        rng, N = self.rng, self.N
        onset = ~self.active & (rng.random(N) < self.p_onset)
        self.active |= onset
        self.h[onset] = 1.0
        self.logr[onset] = rng.uniform(*self.rate_bounds, onset.sum())
        a = self.active
        self.logr[a] += rng.normal(0, self.rate_walk, a.sum())
        self.h[a] -= np.exp(self.logr[a]) + rng.normal(0, self.health_walk, a.sum())
        np.clip(self.h, 0.0, 1.0, out=self.h)

    def _predict(self, rpm, throttle, alt_ft, ambient_c):
        e = self.physics.expected(rpm, throttle, alt_ft, ambient_c)
        h = self.h
        oil = np.where(self.is_lub, h, 1.0)
        cool = np.where(self.is_cool, h, 1.0)
        bear = np.where(self.is_bear, h, 1.0)
        inj = 1.0 - self.inj_onehot * (1.0 - h)[:, None]
        ign = 1.0 - self.ign_onehot * (1.0 - h)[:, None]

        oil_p = e["oil_press_bar"] * oil
        self.oil_t += (e["oil_temp_c"] * (2.0 - cool) - self.oil_t) / 120.0
        self.cht += (e["cht_c"] * (2.0 - cool)[:, None] - self.cht) / 60.0
        self.egt += (e["egt_c"] * (2.0 - inj) - 100.0 * (1.0 - ign) - self.egt) / 5.0
        vib = e["vib_rms_g"] * (2.0 - bear) + 5.0 * (1.0 - ign.mean(axis=1))
        return np.column_stack([oil_p, self.oil_t, self.cht, self.egt, vib])

    def _update(self, pred, y):
        ll = -0.5 * (((y - pred) / self.sigma) ** 2).sum(axis=1)
        ll = ll.reshape(self.M, self.n)
        joint = self.logw + ll
        m = joint.max(axis=1, keepdims=True)
        log_evidence = (m + np.log(np.exp(joint - m).sum(axis=1, keepdims=True))).ravel()
        self.logw = joint - log_evidence[:, None]

        # Bayes over hypotheses, with mixing so none becomes impossible
        pi = np.exp(self.log_pi)
        prior = (1 - self.mix) * pi + self.mix / self.M
        lp = np.log(prior) + log_evidence
        self.log_pi = lp - np.logaddexp.reduce(lp)

    def _resample(self):
        w = np.exp(self.logw)
        ess = 1.0 / (w ** 2).sum(axis=1)
        for m in np.nonzero(ess < self.n / 2)[0]:
            u = (self.rng.random() + np.arange(self.n)) / self.n
            idx = np.minimum(np.searchsorted(np.cumsum(w[m]), u), self.n - 1) + m * self.n
            sl = slice(m * self.n, (m + 1) * self.n)
            for arr in (self.h, self.logr, self.active, self.oil_t):
                arr[sl] = arr[idx]
            self.cht[sl] = self.cht[idx]
            self.egt[sl] = self.egt[idx]
            # roughening keeps particle diversity after duplication
            act = self.active[sl]
            self.logr[sl][act] += self.rng.normal(0, 0.05, act.sum())
            self.logw[m] = -np.log(self.n)

    # ---------------------------------------------------------------------
    def summary(self, horizon_s=3600.0):
        w = np.exp(self.logw).ravel()
        pi = np.exp(self.log_pi)
        degraded = self.active & (self.h < DEGRADED_H)
        d_mass = (np.exp(self.logw) * degraded.reshape(self.M, self.n)).sum(axis=1)
        joint = pi * d_mass  # P(mode m AND degraded)
        p_deg = float(joint.sum())
        post = joint / p_deg if p_deg > 1e-12 else np.full(self.M, 1.0 / self.M)
        m_star = int(np.argmax(post))
        ftype, cyl = MODES[m_star]

        sl = slice(m_star * self.n, (m_star + 1) * self.n)
        wm = np.exp(self.logw[m_star])
        h_q = _weighted_quantiles(self.h[sl], wm, [5, 50, 95])
        out = {
            "p_degraded": round(p_deg, 4),
            "posterior": {"healthy": round(1 - p_deg, 4),
                          **{k: round(float(p * p_deg), 4) for k, p in zip(MODE_KEYS, post)}},
            "map": {"fault": ftype, "cylinder": cyl, "prob": round(float(post[m_star]), 4)},
            "health": {"p5": h_q[0], "p50": h_q[1], "p95": h_q[2]},
            "rate_per_min": None,
            "rul": None,
            "p_fail_horizon": 0.0,
        }

        rul_all = np.full(self.N, np.inf)
        r = np.exp(self.logr)
        rul_all[degraded] = np.maximum(0.0, (self.h[degraded] - self.crit[degraded]) / r[degraded])
        pw = (np.repeat(pi, self.n) * w)
        out["p_fail_horizon"] = round(float((pw * (rul_all < horizon_s)).sum()), 4)

        dm = degraded[sl]
        if dm.any() and wm[dm].sum() > 1e-9:
            out["rate_per_min"] = round(60 * _weighted_quantiles(r[sl][dm], wm[dm], [50])[0], 5)
            q = _weighted_quantiles(rul_all[sl][dm], wm[dm], RUL_QUANTILES)
            out["rul"] = {f"p{k}": round(v, 1) for k, v in zip(RUL_QUANTILES, q)}
        return out

    def run(self, mission_df, report_times, horizon_s=3600.0):
        """mission_df: one mission at 1 Hz indexed by t. Returns
        {t: summary} for every t in report_times."""
        report = set(float(t) for t in report_times)
        Y = mission_df[OBS_COLS].to_numpy(float)
        U = mission_df[["rpm", "throttle_pct", "altitude_ft", "ambient_c"]].to_numpy(float)
        ts = mission_df.index.to_numpy(float)
        self._init_state(Y[0])
        out = {}
        for k in range(1, len(ts)):
            self._propagate()
            pred = self._predict(*U[k])
            self._update(pred, Y[k])
            self._resample()
            if ts[k] in report:
                out[ts[k]] = self.summary(horizon_s)
        return out
