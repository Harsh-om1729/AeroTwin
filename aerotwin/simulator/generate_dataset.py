import os
import pandas as pd
import numpy as np
import yaml
from pathlib import Path
from aerotwin.simulator.engine_model import EngineModel
from aerotwin.simulator.mission_profiles import generate_profile
from aerotwin.simulator.fault_injection import FaultInjector, compute_failure_t

def load_config():
    cfg_path = Path(__file__).parent.parent.parent / "configs" / "engine_rotax912.yaml"
    with open(cfg_path, 'r') as f:
        return yaml.safe_load(f)

def generate_mission_data(airframe_id, mission_id, profile_name, seed, fault_injector=None, gap=0.0, engine_seed=None):
    """gap > 0 flies a GapEngine: a specific engine and sensor set that departs
    from the nominal twin model (see aerotwin.simulator.variation)."""
    cfg = load_config()
    profile = generate_profile(name=profile_name, duration_s=3600)

    rows = []

    # Initialize engine
    # In a fault run, fault might start at 1000s. We evaluate health at each step.
    if gap > 0:
        from aerotwin.simulator.variation import GapEngine
        engine = GapEngine(cfg, seed, gap, engine_seed=engine_seed)
    else:
        engine = EngineModel(cfg, seed)
    
    for i, t in enumerate(profile["t"]):
        # Update health if fault injected
        if fault_injector:
            engine.health = fault_injector.get_health(t)
            
        row = engine.step(
            rpm=profile["rpm"][i],
            throttle=profile["throttle_pct"][i],
            alt_ft=profile["altitude_ft"][i],
            ambient_c=profile["ambient_c"][i],
            dt=1.0
        )
        
        row["airframe_id"] = airframe_id
        row["mission_id"] = mission_id
        row["t"] = t
        row["phase"] = profile["phase"][i]
        
        rows.append(row)
        
    return pd.DataFrame(rows)

# Bump whenever the simulator physics or the split recipe changes; recorded
# in the fault logs so results can be traced to the data that produced them.
DATASET_VERSION = "2.0"

FAULTS = [
    ("lubrication", 0.001),
    ("cooling_degradation", 0.002),
    ("injector_abnormality", 0.003),
    ("misfire", 0.005),
    ("abnormal_vibration", 0.002),
]


def _seeded_mission(airframe_id, mission_id, profile, seed, fault_injector=None):
    # the rapid_throttle profile draws from the global RNG; pin it per mission
    np.random.seed(seed % 2**32)
    return generate_mission_data(airframe_id, mission_id, profile, seed=seed, fault_injector=fault_injector)


def _healthy_split(prefix, airframes, missions, profile, seed_base):
    return pd.concat([
        _seeded_mission(f"UAV-{af:02d}", f"{prefix}_{af}_{m}", profile, seed=seed_base * 100_000 + af * 1000 + m)
        for af in airframes for m in missions
    ])


def _fault_split(name, airframes, runs_per_fault, seed_base):
    """Every flight gets its own seed (no noise sequence is shared between
    fault types), and fault onsets come from a seeded generator, so the split
    is identical on every machine."""
    rng = np.random.default_rng(seed_base)
    dfs, logs = [], []
    for af in airframes:
        for fi, (ftype, rate) in enumerate(FAULTS):
            for m in range(runs_per_fault):
                seed = seed_base * 100_000 + af * 1000 + fi * 100 + m
                mission_id = f"{name}_{af}_{ftype}_{m}"
                start_t = int(rng.integers(500, 2000))
                df = _seeded_mission(f"UAV-{af:02d}", mission_id, "standard", seed,
                                     FaultInjector(ftype, start_t, rate))
                dfs.append(df)
                logs.append({
                    "mission_id": mission_id,
                    "fault_type": ftype,
                    "fault_start_t": start_t,
                    "severity": rate,
                    "failure_t": compute_failure_t(ftype, start_t, rate),
                    "seed": seed,
                    "dataset_version": DATASET_VERSION,
                })
    return pd.concat(dfs), pd.DataFrame(logs)


def main():
    """Splits (seeds are disjoint by construction: seed_base differs):

      train_healthy  UAV-01..07, 20 flights each, standard profile   -> fit models
      val_healthy    UAV-01..07, 4 flights each                      -> fusion + HI calibration
      val_fault      UAV-11..12, 5 faults x 2 runs                   -> the ONLY fault data used
                                                                        while developing rules/thresholds
      test_healthy   UAV-08..10, 20 flights each, hot-weather profile -> false alarms (final)
      test_fault     UAV-08..10, 5 faults x 4 runs                   -> final numbers, evaluated once
    """
    out_dir = Path(__file__).parent.parent.parent / "data"
    out_dir.mkdir(exist_ok=True)

    print("Generating train_healthy...")
    _healthy_split("train", range(1, 8), range(20), "standard", seed_base=1).to_parquet(out_dir / "train_healthy.parquet")
    print("Generating val_healthy...")
    _healthy_split("val", range(1, 8), range(20, 24), "standard", seed_base=2).to_parquet(out_dir / "val_healthy.parquet")
    print("Generating test_healthy...")
    _healthy_split("test", range(8, 11), range(20), "hot_weather", seed_base=3).to_parquet(out_dir / "test_healthy.parquet")

    print("Generating val_fault...")
    df, log = _fault_split("valfault", range(11, 13), 2, seed_base=4)
    df.to_parquet(out_dir / "val_fault.parquet")
    log.to_csv(out_dir / "val_fault_log.csv", index=False)

    print("Generating test_fault...")
    df, log = _fault_split("fault", range(8, 11), 4, seed_base=5)
    df.to_parquet(out_dir / "test_fault.parquet")
    log.to_csv(out_dir / "fault_log.csv", index=False)

    print(f"Data generation complete (dataset version {DATASET_VERSION}).")


if __name__ == "__main__":
    main()
