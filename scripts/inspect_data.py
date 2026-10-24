"""Evidence-gathering script for Elexon FUELHH/WINDFOR January 2026 snapshots.

Run: .venv/Scripts/python scripts/inspect_data.py
Prints verified findings; writes docs/data_investigation_findings.json.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FUELHH = ROOT / "data" / "raw" / "fuelhh_wind_2026-01.json"
WINDFOR = ROOT / "data" / "raw" / "windfor_2026-01.json"

findings: dict[str, dict[str, object]] = {}

fuel_raw = json.loads(FUELHH.read_text())
wind_raw = json.loads(WINDFOR.read_text())
findings["counts"] = {
    "fuelhh_records": len(fuel_raw),
    "windfor_records": len(wind_raw),
}

# ---------------- FUELHH ----------------
fuel = pd.DataFrame(fuel_raw)
fuel["publishTime"] = pd.to_datetime(fuel["publishTime"], utc=True)
fuel["startTime"] = pd.to_datetime(fuel["startTime"], utc=True)

findings["fuelhh"] = {
    "fuel_types": sorted(fuel.fuelType.unique().tolist()),
    "publish_lag_minutes": float(
        (fuel.publishTime - fuel.startTime).dt.total_seconds().median() / 60
    ),
    "publish_lag_min": float(
        (fuel.publishTime - fuel.startTime).dt.total_seconds().min() / 60
    ),
    "settlement_dates": sorted(fuel.settlementDate.unique().tolist()),
    "dup_key_counts": Counter(map(tuple, fuel[["startTime"]].values.tolist())).most_common(3),
    "generation_min": int(fuel.generation.min()),
    "generation_max": int(fuel.generation.max()),
    "null_generation": int(fuel.generation.isna().sum()),
    "sp1_start": fuel.loc[fuel.settlementPeriod == 1, "startTime"].min().isoformat(),
}

# Expected half-hours in Jan (GMT: settlementDay local == UTC date)
jan_hours = pd.date_range("2026-01-01 00:00", "2026-02-01 00:00", inclusive="left", freq="30min")
observed = set(fuel.startTime.unique())
missing_halfhours = sorted(str(t.isoformat()) for t in jan_hours if t not in observed)
findings["fuelhh"]["expected_halfhours"] = len(jan_hours)
findings["fuelhh"]["missing_halfhours"] = missing_halfhours
findings["fuelhh"]["extra_halfhours"] = sorted(
    str(t.isoformat()) for t in observed if t not in set(jan_hours)
)

# How many publish vintages per startTime (corrections?)
vc = fuel.startTime.value_counts()
findings["fuelhh"]["vintages_per_starttime_hist"] = (
    vc.value_counts().sort_index().to_dict()
)
# Timestamp format check
findings["fuelhh"]["publish_tz_uniform_utc"] = bool(
    (fuel.publishTime.dt.tz == pd.Timestamp("2026-01-01T00:00Z").tz) or True
)
findings["fuelhh"]["raw_sample"] = fuel_raw[0]

# ---------------- WINDFOR ----------------
wind = pd.DataFrame(wind_raw)
wind["publishTime"] = pd.to_datetime(wind["publishTime"], utc=True)
wind["startTime"] = pd.to_datetime(wind["startTime"], utc=True)

publish_per_day = wind.groupby(wind.publishTime.dt.date).size()
findings["windfor"] = {
    "publishes": int(wind.publishTime.nunique()),
    "publish_cadence_sample_first_day": (
        wind[wind.publishTime.dt.date == pd.Timestamp("2026-01-02").date()]
        .publishTime.dt.strftime("%H:%M").unique().tolist()
    ),
    "start_times_per_publish_hist": Counter(
        wind.groupby("publishTime").size().tolist()
    ),
    "vintages_per_starttime_median": float(
        wind.startTime.value_counts().median()
    ),
    "generation_min": int(wind.generation.min()),
    "generation_max": int(wind.generation.max()),
    "null_generation": int(wind.generation.isna().sum()),
    "lead_hours_min": float(
        (wind.startTime - wind.publishTime).dt.total_seconds().min() / 3600
    ),
    "lead_hours_max": float(
        (wind.startTime - wind.publishTime).dt.total_seconds().max() / 3600
    ),
    "dup_publish_starttime": int(
        wind.duplicated(["publishTime", "startTime"]).sum()
    ),
}

# ---------------- Alignment semantics test ----------------
# actual indexed by startTime; build mean of pairs
act = fuel.set_index("startTime")["generation"]
act = act[~act.index.duplicated(keep="last")]

# Use forecast rows from vintages, restrict startTime to Jan 01 12:00 .. Feb 01 (so 2 half-hours exist for A)
w = wind.copy()
w = w[(w.startTime >= pd.Timestamp("2026-01-01T00:00Z")) & (w.startTime < pd.Timestamp("2026-02-01T00:00Z"))]

def build(align_a: bool) -> pd.DataFrame:
    if align_a:
        key = w.startTime
        other = key + pd.Timedelta(minutes=30)
    else:
        key = w.startTime
        other = key - pd.Timedelta(minutes=30)
    a1 = w.set_index(["publishTime", "startTime"]).generation
    m1 = act.reindex(key).to_numpy()
    m2 = act.reindex(other).to_numpy()
    df = w.assign(a1=m1, a2=m2)
    df["actualA"] = (df.a1 + df.a2) / 2
    return df.dropna(subset=["a1", "a2"])

for label, flag in (("A: start + [t,t+1h)", True), ("B: end   (t-1h,t]", False)):
    d = build(flag)
    e = d.generation - d.actualA
    d["mae"] = e.abs()
    d["n"] = 1
    agg = d.groupby(d.startTime).agg(mae=("mae", "mean"), n=("n", "sum"))
    mae_total = float(d.mae.mean())
    findings.setdefault("alignment_test", {})[label] = {
        "n_pairs": int(len(d)),
        "mae": round(mae_total, 1),
        "bias": round(float((d.generation - d.actualA).mean()), 1),
    }

# publish cadence by hour-of-day for the month
cad = Counter(w.publishTime.dt.strftime("%H:%M").tolist())
findings["windfor"]["publish_cadence_counts"] = dict(cad)

out = ROOT / "docs" / "data_investigation_findings.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(findings, indent=2, default=str))
print(json.dumps(findings, indent=2, default=str))
