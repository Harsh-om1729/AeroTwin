"""Tuning harness for the particle filter.

Uses ONLY freshly simulated flights (seeds disjoint from the dataset, random
onsets and severities) -- the held-out test set is never touched here, so
test-set numbers in the validation report stay honest.

    python3 -m aerotwin.twin.tune
"""
import itertools
import time

import numpy as np

from aerotwin.simulator.fault_injection import FaultInjector, compute_failure_t, degrade
from aerotwin.simulator.generate_dataset import generate_mission_data, load_config
from aerotwin.twin.particle_filter import HealthParticleFilter

BASE = {"lubrication": 0.001, "cooling_degradation": 0.002, "injector_abnormality": 0.003,
        "misfire": 0.005, "abnormal_vibration": 0.002}
TRUE_CYL = {"injector_abnormality": 1, "misfire": 2}


def tuning_flights(n_per_fault=2, n_healthy=3, seed=424242):
    rng = np.random.default_rng(seed)
    flights = []
    for i in range(n_healthy):
        flights.append((None, None, None, 900_000 + i))
    for ft in BASE:
        for j in range(n_per_fault):
            rate = BASE[ft] * rng.choice([0.5, 1.0, 2.0])
            flights.append((ft, int(rng.integers(600, 2400)), rate, 910_000 + 10 * j + len(flights)))
    return flights


def evaluate(params, flights, cfg):
    stats = {"false": 0, "delay": [], "diag": [], "h_err": [], "cover": [], "rel_err": []}
    for ft, t0, rate, seed in flights:
        np.random.seed(seed % 2**31)
        fi = FaultInjector(ft, t0, rate) if ft else None
        df = generate_mission_data("T", "t", "standard", seed=seed, fault_injector=fi).set_index("t")
        res = HealthParticleFilter(cfg, **params).run(df, df.index[59::10])
        alarms = [t for t, s in sorted(res.items()) if s["p_degraded"] > 0.95]
        if ft is None:
            stats["false"] += bool(alarms)
            continue
        fail = compute_failure_t(ft, t0, rate)
        pre = [t for t in alarms if t < t0]
        stats["false"] += bool(pre)
        post = [t for t in alarms if t >= t0]
        if not post:
            stats["delay"].append(np.inf)
            continue
        stats["delay"].append(post[0] - t0)
        m = res[post[0]]["map"]
        stats["diag"].append(m["fault"] == ft and m["cylinder"] == TRUE_CYL.get(ft))
        shape = "lin" if ft == "misfire" else "exp"
        for t, s in res.items():
            if post[0] <= t < fail:
                stats["h_err"].append(abs(s["health"]["p50"] - degrade(t, t0, rate, shape)))
                if s["rul"]:
                    true = fail - t
                    stats["cover"].append(s["rul"]["p5"] <= true <= s["rul"]["p95"])
                    stats["rel_err"].append(abs(s["rul"]["p50"] - true) / max(true, 30))
    return {
        "false_flights": stats["false"],
        "median_delay_s": float(np.median(stats["delay"])),
        "diag_acc": float(np.mean(stats["diag"])),
        "h_mae": float(np.mean(stats["h_err"])),
        "cover90": float(np.mean(stats["cover"])),
        "rul_rel_err": float(np.median(stats["rel_err"])),
    }


if __name__ == "__main__":
    cfg = load_config()
    flights = tuning_flights()
    grid = {
        "health_walk": [2e-4, 2e-3, 5e-3],
        "rate_walk": [0.02, 0.1],
        "p_onset": [0.002, 0.01],
    }
    for combo in itertools.product(*grid.values()):
        params = dict(zip(grid, combo))
        t = time.time()
        r = evaluate(params, flights, cfg)
        print(params, {k: round(v, 3) for k, v in r.items()}, f"{time.time() - t:.0f}s", flush=True)
