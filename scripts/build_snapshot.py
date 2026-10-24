"""Builds the reproducible canonical snapshot from the documented raw files.

Usage:
  .venv/Scripts/python scripts/build_snapshot.py            # from data/raw
  .venv/Scripts/python scripts/build_snapshot.py --live     # fetch via API first

Outputs data/snapshots/latest/{fuelhh_wind.json, windfor.json, manifest.json}.
Input validation, filtering, dedupe and timestamp normalisation run through the
same backend code paths used at request time (backend/app/services/*).
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import Settings  # noqa: E402
from app.services.dataset import ForecastDataset  # noqa: E402
from app.services.elexon_client import ElexonClient  # noqa: E402

RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "snapshots" / "latest"
PERIOD_START = date(2026, 1, 1)
PERIOD_END = date(2026, 1, 31)
PUBLICATION_FROM = datetime(2025, 12, 30, 0, 0, tzinfo=timezone.utc)
PUBLICATION_TO = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)

ALIGNMENT_NOTE = (
    "WINDFOR startTime T labels the hour ENDING at T (interval [T-1h, T)); "
    "hourly MW applied to both half-hours of that hour. Empirically resolved "
    "on January 2026 data (docs/DATA_INVESTIGATION.md); raw labels retained."
)
CUTOFF_NOTE = {
    "default_preset": "day_ahead_1030",
    "presets": ["day_ahead_1030", "day_ahead_gate_0950", "intraday_auction_1730"],
    "rationale": "Day-ahead procurement finalisation after the N2EX day-ahead "
    "auction results publish (gate 09:50 GMT D-1, results by 10:00 GMT; Nord "
    "Pool). Analytical assumption, configurable per request.",
}


def fetch_live() -> tuple[list[dict], list[dict]]:
    client = ElexonClient(Settings())
    try:
        actuals = client.fetch_fuelhh_wind(PERIOD_START.isoformat(), PERIOD_END.isoformat())
        forecasts = client.fetch_windfor(PUBLICATION_FROM.isoformat(), PUBLICATION_TO.isoformat())
    finally:
        client.close()
    return actuals, forecasts


def verify_invariants(actual_records: list[dict], forecast_records: list[dict]) -> dict:
    dataset = ForecastDataset.from_records(actual_records, forecast_records, {})
    actuals = dataset.actuals
    expected_count = (PERIOD_END - PERIOD_START).days * 48 + 48
    missing = []
    day = PERIOD_START
    while day <= PERIOD_END:
        for period in range(48):
            import datetime as _dt

            iso_day_start = _dt.datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
            stamp = iso_day_start + _dt.timedelta(minutes=period * 30)
            if stamp not in actuals:
                missing.append(stamp.isoformat())
        day += timedelta(days=1)
    problems = []
    if missing:
        problems.append(f"missing half-hours: {len(missing)} ({missing[:3]}...)")
    if actuals:
        assert min(actuals) >= PUBLICATION_FROM
    return {
        "expected_halfhours": expected_count,
        "actual_rows": len(actual_records),
        "distinct_intervals": len(actuals),
        "windfor_rows": len(forecast_records),
        "windfor_publishes": len({r["publishTime"] for r in forecast_records}),
        "missing_halfhours": missing,
        "problems": problems,
    }


def build() -> None:
    if "--live" in sys.argv:
        actual_records, forecast_records = fetch_live()
        RAW.mkdir(parents=True, exist_ok=True)
        (RAW / "fuelhh_wind_2026-01.json").write_text(json.dumps(actual_records))
        (RAW / "windfor_2026-01.json").write_text(json.dumps(forecast_records))
        source = "Elexon BMRS v1 API (fetched via backend client); persisted to data/raw for offline rebuilds"
        retrieved_at = datetime.now(timezone.utc).isoformat()
    else:
        actual_path = RAW / "fuelhh_wind_2026-01.json"
        forecast_path = RAW / "windfor_2026-01.json"
        actual_records = json.loads(actual_path.read_text())
        forecast_records = json.loads(forecast_path.read_text())
        source = (
            "Elexon BMRS v1 API; /datasets/FUELHH/stream (fuelType=WIND, "
            "settlementDate 2026-01-01..2026-01-31) and /datasets/WINDFOR/stream "
            "(publishDateTimeFrom=2025-12-30T00:00Z to 2026-02-01T00:00Z)"
        )
        retrieved_at = "2026-10-23T00:00:00Z"

    invariants = verify_invariants(actual_records, forecast_records)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "fuelhh_wind.json").write_text(json.dumps(actual_records, separators=(",", ":")))
    (OUT / "windfor.json").write_text(json.dumps(forecast_records, separators=(",", ":")))

    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    manifest = {
        "source": source,
        "retrieved_at_utc": retrieved_at,
        "period": {
            "settlement_from": PERIOD_START.isoformat(),
            "settlement_to": PERIOD_END.isoformat(),
            "publication_window_utc": [PUBLICATION_FROM.isoformat(), PUBLICATION_TO.isoformat()],
        },
        "counts": {
            "fuelhh_wind_rows": len(actual_records),
            "windfor_rows": len(forecast_records),
            "windfor_publishes": invariants["windfor_publishes"],
            "distinct_actual_intervals": invariants["distinct_intervals"],
            "expected_halfhours": invariants["expected_halfhours"],
        },
        "processing": [
            "filter fuelType == 'WIND' (server-side on FUELHH retrieval)",
            "parse ISO-8601 UTC timestamps; settlement fields are Europe/London",
            "dedupe FUELHH per startTime: latest publishTime wins (re-release policy)",
            "dedupe WINDFOR per (publishTime, startTime): later source order wins",
            "no rescaling or gap-filling; missing values stay missing",
        ],
        "alignment_convention": ALIGNMENT_NOTE,
        "cutoff_assumption": CUTOFF_NOTE,
        "invariants": invariants,
        "checksums": {
            "fuelhh_wind.json": sha(OUT / "fuelhh_wind.json"),
            "windfor.json": sha(OUT / "windfor.json"),
        },
        "notes": [
            "Systematic view difference: WINDFOR (system-operator national view incl. "
            "embedded wind) ran ~+16% above FUELHH WIND (settlement-visible BM wind) in "
            "Jan-2026 backfills. Metrics are reported on the two mandated datasets as-is.",
            "Analysis period: January 2026 (GB procurement month for the challenge).",
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))
    if invariants["problems"]:
        print("INVARIANT PROBLEMS DETECTED", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    build()
