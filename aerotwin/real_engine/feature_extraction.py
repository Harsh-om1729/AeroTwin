"""Loads the NGAFID Aviation Maintenance Dataset (real Cessna 172 flights).

Paper: Yang & Desell 2022, https://arxiv.org/abs/2210.07317. Download from
https://doi.org/10.5281/zenodo.6624956 and extract anywhere under data/.

Facts checked against the files themselves:
  * flight data: one_parq/*.parquet, rows NOT in time order, keyed by "Master
    Index"; temperatures in F (OAT in C), oil pressure in psi, fuel in gal/h.
  * 2days/flight_header.csv is the authors' benchmark subset: before_after 1 =
    within 2 days before unplanned maintenance, 0 = within 2 days after.
  * there is no maintenance-event or aircraft id. Each issue type was cut into
    5 long blocks of consecutive flights to make `fold`, so a repair rarely
    crosses folds, but about 1% do. infer_repair_groups rebuilds approximate
    repairs from flight order; flights of a group spanning folds are dropped so
    no repair leaks, and groups are the bootstrap unit. They over-split
    (5,614 groups for 2,111 real events), so CIs may be slightly narrow, and an
    aircraft can still appear in several folds.

2days/flight_data.pkl is deliberately never read: a pickle can execute code,
and the parquet files hold the same flights.
"""
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

F_TO_C = lambda f: (f - 32.0) * 5.0 / 9.0
PSI_TO_BAR = 0.0689476
GAL_TO_L = 3.78541

SOURCE_COLS = ["Master Index", "timestep", "E1 RPM", "E1 FFlow", "E1 OilT", "E1 OilP", "OAT", "IAS", "VSpd", "AltMSL",
               *[f"E1 CHT{i}" for i in range(1, 5)], *[f"E1 EGT{i}" for i in range(1, 5)]]
SENSORS = ["oil_temp_c", "oil_press_bar", *[f"cht_{i}" for i in range(1, 5)], *[f"egt_{i}" for i in range(1, 5)]]
COVARIATES = ["rpm", "fuel_flow_lph", "ambient_c", "altitude_ft", "vspd_fpm", "ias_kt",
              "rpm_lag", "fuel_lag", "t_since_start"]

BLOCK_S = 10            # flights are averaged into 10 s blocks
MIN_RPM, MIN_IAS = 1800.0, 50.0   # airborne, engine under load
WARMUP_S = 300          # thermal transient after start-up
MIN_AIRBORNE_S = 600
LAG_S = 120             # time scale of the thermal-lag covariates
ISSUE_OTHER = "intake_rocker_other"


def find_root(data_dir):
    """Folder holding all_flights/ and 2days/, wherever it was extracted under data/."""
    data_dir = Path(data_dir)
    for header in sorted(data_dir.glob("**/2days/2days/flight_header.csv")):
        root = header.parents[2]
        if (root / "all_flights" / "all_flights" / "one_parq").is_dir():
            return root
    raise FileNotFoundError(f"NGAFID not found under {data_dir}; download it from "
                            "https://doi.org/10.5281/zenodo.6624956 and extract it there.")


def infer_repair_groups(header):
    """Flights are listed issue by issue, and within an issue repair by repair
    (before ... after). A new group starts when the issue changes or a "before"
    flight follows an "after" one. header: Master Index, label, before_after."""
    h = header.sort_values("Master Index")
    groups, cur, after_seen, prev = [], 0, False, None
    for label, ba in zip(h["label"], h["before_after"]):
        if label != prev or (ba == "before" and after_seen):
            cur, after_seen = cur + 1, False
        after_seen = after_seen or ba == "after"
        prev = label
        groups.append(cur)
    return pd.Series(groups, index=h["Master Index"].to_numpy(), name="event_group")


def load_header(root):
    """One row per benchmark flight: flight, before (1/0), fold, event_group,
    issue, label; flights of repairs spanning more than one fold are removed."""
    root = Path(root)
    h = pd.read_csv(root / "2days" / "2days" / "flight_header.csv").sort_values("Master Index")
    groups = infer_repair_groups(pd.read_csv(root / "all_flights" / "all_flights" / "flight_header.csv"))
    h = pd.DataFrame({
        "flight": h["Master Index"].to_numpy(),
        "before": h["before_after"].to_numpy(),
        "fold": h["fold"].to_numpy(),
        "event_group": groups.loc[h["Master Index"]].to_numpy(),
        "issue": h["hierarchy"].fillna(ISSUE_OTHER).to_numpy(),
        "label": h["label"].to_numpy(),
    })
    return h[h.groupby("event_group")["fold"].transform("nunique") == 1].reset_index(drop=True)


def to_si(df):
    """Raw NGAFID columns -> AeroTwin names and units."""
    out = pd.DataFrame({
        "flight": df["Master Index"].to_numpy(),
        "t": df["timestep"].to_numpy(),
        "rpm": df["E1 RPM"].to_numpy(),
        "fuel_flow_lph": df["E1 FFlow"].to_numpy() * GAL_TO_L,
        "oil_temp_c": F_TO_C(df["E1 OilT"].to_numpy()),
        "oil_press_bar": df["E1 OilP"].to_numpy() * PSI_TO_BAR,
        "ambient_c": df["OAT"].to_numpy(),
        "ias_kt": df["IAS"].to_numpy(),
        "vspd_fpm": df["VSpd"].to_numpy(),
        "altitude_ft": df["AltMSL"].to_numpy(),
    })
    for i in range(1, 5):
        out[f"cht_{i}"] = F_TO_C(df[f"E1 CHT{i}"].to_numpy())
        out[f"egt_{i}"] = F_TO_C(df[f"E1 EGT{i}"].to_numpy())
    return out


def resample_flight(f):
    """One flight (SI columns, any row order) -> 10 s blocks of steady airborne
    flight, or None if too little of it is usable. A sensor missing for most of
    the flight rejects it (CHT 2-4 are absent on about 5% of flights)."""
    f = f.sort_values("t").reset_index(drop=True)
    if f[SENSORS].isna().mean().max() > 0.10:
        return None
    running = f["rpm"] > 1000
    if not running.any():
        return None
    f = f.copy()
    f["t_since_start"] = f["t"] - f.loc[running.idxmax(), "t"]
    f["rpm_lag"] = f["rpm"].ewm(halflife=LAG_S, min_periods=1).mean()
    f["fuel_lag"] = f["fuel_flow_lph"].ewm(halflife=LAG_S, min_periods=1).mean()
    keep = (f["rpm"] >= MIN_RPM) & (f["ias_kt"] >= MIN_IAS) & (f["t_since_start"] >= WARMUP_S)
    f = f[keep]
    if len(f) < MIN_AIRBORNE_S:
        return None
    f = f.assign(block=f["t"] // BLOCK_S)
    b = f.groupby("block")[SENSORS + COVARIATES].mean().dropna()
    if len(b) * BLOCK_S < MIN_AIRBORNE_S:
        return None
    b = b.reset_index()
    b["segment"] = (b["block"].diff() != 1).cumsum()  # windows never cross a gap
    b.insert(0, "flight", f["flight"].iloc[0])
    return b.astype({c: "float32" for c in SENSORS + COVARIATES})


def prepare(root, out_path):
    """Reduces all benchmark flights to 10 s blocks, once (~100M rows -> one small
    parquet). Returns (blocks, stats)."""
    header = load_header(root)
    wanted = set(header["flight"].tolist())
    parts, seen = [], 0
    for path in sorted((Path(root) / "all_flights" / "all_flights" / "one_parq").glob("*.parquet")):
        raw = pq.read_table(path, columns=SOURCE_COLS).to_pandas()
        raw = raw.reset_index(drop=raw.index.name != "Master Index") if "Master Index" not in raw else raw
        raw = raw[raw["Master Index"].isin(wanted)]
        for _, g in to_si(raw).groupby("flight", sort=False):
            seen += 1
            b = resample_flight(g)
            if b is not None:
                parts.append(b)
    blocks = pd.concat(parts, ignore_index=True)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    blocks.to_parquet(out_path)
    return blocks, {"flights_in_benchmark": len(wanted), "flights_read": seen, "flights_usable": len(parts)}


__all__ = ["find_root", "infer_repair_groups", "load_header", "to_si", "resample_flight", "prepare", "SENSORS", "COVARIATES", "BLOCK_S"]
