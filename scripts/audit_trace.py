"""Independent audit trace: re-implements the domain rules from the RAW snapshot
files alone, then compares with the service code path (loader/dataset/metrics).
Evidence for docs/PRE_SUBMISSION_AUDIT.md - if the independent parse and the
hand maths agree with the service path, displayed numbers are traceable to
source records.

Usage: python scripts/audit_trace.py [snapshot_dir] [delivery_date]
"""
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SNAPSHOT = Path(sys.argv[1] if len(sys.argv) > 1 else "data/snapshots/latest")
DAY = sys.argv[2] if len(sys.argv) > 2 else "2026-01-15"


def iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def parse_generation(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


fuel = json.loads((SNAPSHOT / "fuelhh_wind.json").read_text(encoding="utf-8"))
wind = json.loads((SNAPSHOT / "windfor.json").read_text(encoding="utf-8"))

# --- actuals: WIND only, latest publishTime wins per half-hour ---------------
actuals: dict[datetime, float] = {}
publish_by_start: dict[datetime, datetime] = {}
for rec in fuel:
    if rec.get("fuelType") != "WIND":
        continue
    start, publish = iso(rec["startTime"]), iso(rec["publishTime"])
    gen_v = parse_generation(rec.get("generation"))
    if gen_v is None:
        continue
    if start not in publish_by_start or publish >= publish_by_start[start]:
        publish_by_start[start] = publish
        actuals[start] = gen_v

# --- interval set: 48 half-hours of the London delivery day (January = GMT) --
day = datetime.fromisoformat(DAY)
day_utc = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
intervals = [day_utc + timedelta(minutes=30 * i) for i in range(48)]
interval_set = set(intervals)

# --- label convention (independently re-derived from raw data) ---------------
# WINDFOR startTime values are on the full hour (empirical check below) and
# label the hour ENDING at T; every half-hour interval maps to the hourly
# vintage of its containing hour: label = floor(interval_start)+1h.
minutes_seen = sorted({iso(rec["startTime"]).minute for rec in wind})
hourly_labels = ",".join(str(m) for m in minutes_seen)

def hour_end_label(interval_start: datetime) -> datetime:
    return interval_start.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

# --- forecasts: winner = argmax publish <= cutoff among hour-ending labels ---
cutoff = day_utc - timedelta(hours=13, minutes=30)  # day_ahead_1030: D-1 10:30 London (GMT in Jan)
winners: dict[datetime, float] = {}
win_publish: dict[datetime, datetime] = {}
publications_scanned = 0
excluded_after_cutoff = 0
null_generation_records = 0
candidates_by_label: dict[datetime, list[tuple[datetime, float]]] = {}
for rec in wind:
    hour_end = iso(rec["startTime"])
    if hour_end not in {hour_end_label(i) for i in intervals}:
        continue
    publish = iso(rec["publishTime"])
    publications_scanned += 1
    gen_v = parse_generation(rec.get("generation"))
    if gen_v is None:
        null_generation_records += 1
        continue
    candidates_by_label.setdefault(hour_end, []).append((publish, gen_v))
    if publish > cutoff:
        excluded_after_cutoff += 1
        continue
    known = win_publish.get(hour_end)
    if known is None or publish >= known:
        win_publish[hour_end] = publish
        winners[hour_end] = gen_v

# --- metrics by hand ---------------------------------------------------------
pairs = [(winners[hour_end_label(i)], actuals[i]) for i in intervals if hour_end_label(i) in winners and i in actuals]
errors = [f - a for f, a in pairs]
mae = round(sum(abs(e) for e in errors) / len(errors), 1) if errors else None
rmse = round(math.sqrt(sum(e * e for e in errors) / len(errors)), 1) if errors else None
bias = round(sum(errors) / len(errors), 1) if errors else None

print(f"day={DAY} expected_intervals=48")
print(f"windfor_label_minutes[{hourly_labels}] (hour-ending on-the-hour labels)")
sample_label = hour_end_label(intervals[0])
elig = [(p.isoformat(), g) for p, g in sorted(candidates_by_label.get(sample_label, []))]
picked = max([c for c in elig if iso(c[0]) <= cutoff], key=lambda c: c[0]) if elig else None
post = [c[0] for c in elig if iso(c[0]) > cutoff]
print(f"sample interval {intervals[0].isoformat()} label {sample_label.isoformat()}: "
      f"{len(elig)} records, {len(post)} published after cutoff, winner publish={picked[0] if picked else None}")
print(f"actuals_available={sum(1 for i in intervals if i in actuals)}/48")
print(f"eligible_forecasts={sum(1 for i in intervals if hour_end_label(i) in winners)}/48")
print(f"valid_pairs={len(pairs)} publications_scanned={publications_scanned} excluded_after_cutoff={excluded_after_cutoff} null_generation={null_generation_records}")
print(f"cutoff_utc={cutoff.isoformat().replace('+00:00', 'Z')}")
print(f"HAND-CALC mae={mae} rmse={rmse} bias={bias}")

# --- compare with the service path ------------------------------------------
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "backend"))

from app.services.dataset import ForecastDataset  # noqa: E402
from app.services.accuracy import CutoffPolicy, coverage, cutoff_for_day, summary_metrics  # noqa: E402

dataset = ForecastDataset.from_snapshot(SNAPSHOT)
policy = CutoffPolicy(preset="day_ahead_1030")
service_cutoff = cutoff_for_day(day, policy)
points = dataset.compute_interval_points(day, service_cutoff)
res = summary_metrics(points)
cov = coverage(points)
print(f"SERVICE   cutoff={service_cutoff.isoformat().replace('+00:00', 'Z')}")
print(f"SERVICE   mae={res.mae_mw} rmse={res.rmse_mw} bias={res.mean_bias_mw}")
print(f"SERVICE   coverage={cov.to_dict()}")

agree = (
    mae == res.mae_mw
    and rmse == res.rmse_mw
    and bias == res.mean_bias_mw
    and len(pairs) == cov.valid_pairs
    and service_cutoff == cutoff
)
print(f"TRACE {'AGREES' if agree else 'MISMATCH'} with service path")
if not agree:
    raise SystemExit(1)
