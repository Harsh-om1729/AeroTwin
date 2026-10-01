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

def generate_mission_data(airframe_id, mission_id, profile_name, seed, fault_injector=None):
    cfg = load_config()
    profile = generate_profile(name=profile_name, duration_s=3600)
    
    # Pre-allocate rows
    rows = []
    
    # Initialize engine
    # In a fault run, fault might start at 1000s. We evaluate health at each step.
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

def main():
    out_dir = Path(__file__).parent.parent.parent / "data"
    out_dir.mkdir(exist_ok=True)
    
    # Generate healthy train missions (Airframes 1-7)
    print("Generating train_healthy...")
    train_dfs = []
    for af in range(1, 8):
        for m in range(20):
            df = generate_mission_data(f"UAV-{af:02d}", f"train_{af}_{m}", "standard", seed=af*100+m)
            train_dfs.append(df)
    pd.concat(train_dfs).to_parquet(out_dir / "train_healthy.parquet")
    
    # Generate val healthy
    print("Generating val_healthy...")
    val_dfs = []
    for af in range(1, 8):
        for m in range(20, 24):
            df = generate_mission_data(f"UAV-{af:02d}", f"val_{af}_{m}", "standard", seed=af*100+m)
            val_dfs.append(df)
    pd.concat(val_dfs).to_parquet(out_dir / "val_healthy.parquet")

    # Generate test healthy (Airframes 8-10)
    print("Generating test_healthy...")
    test_dfs = []
    for af in range(8, 11):
        for m in range(20):
            df = generate_mission_data(f"UAV-{af:02d}", f"test_{af}_{m}", "hot_weather", seed=af*100+m)
            test_dfs.append(df)
    pd.concat(test_dfs).to_parquet(out_dir / "test_healthy.parquet")

    # Generate fault runs
    print("Generating test_fault...")
    faults = [
        ("lubrication", 0.001),
        ("cooling_degradation", 0.002),
        ("injector_abnormality", 0.003),
        ("misfire", 0.005),
        ("abnormal_vibration", 0.002)
    ]
    
    fault_logs = []
    fault_dfs = []
    
    for af in range(8, 11):
        for i, (ftype, rate) in enumerate(faults):
            for m in range(4): # 4 runs per fault per airframe
                mission_id = f"fault_{af}_{ftype}_{m}"
                start_t = np.random.randint(500, 2000)
                fi = FaultInjector(ftype, start_t, rate)
                df = generate_mission_data(f"UAV-{af:02d}", mission_id, "standard", seed=af*1000+m, fault_injector=fi)
                fault_dfs.append(df)
                fault_logs.append({
                    "mission_id": mission_id,
                    "fault_type": ftype,
                    "fault_start_t": start_t,
                    "severity": rate,
                    "failure_t": compute_failure_t(ftype, start_t, rate)
                })
                
    pd.concat(fault_dfs).to_parquet(out_dir / "test_fault.parquet")
    pd.DataFrame(fault_logs).to_csv(out_dir / "fault_log.csv", index=False)
    
    print("Data generation complete.")

if __name__ == "__main__":
    main()
