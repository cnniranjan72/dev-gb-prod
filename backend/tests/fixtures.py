from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
DAY_START = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)


def _stamp(offset_minutes: int) -> str:
    return (DAY_START + timedelta(minutes=offset_minutes)).isoformat().replace("+00:00", "Z")


def synthetic_actual_records() -> list[dict]:
    """FUELHH WIND rows for the 2026-01-15 GB settlement day.

    Deliberately imperfect dataset:
      * half-hour starting 05:00Z (index 10, period 11) is MISSING entirely;
      * half-hour starting 08:00Z (index 16, period 17) carries generation=None.
    Gives 46 records for 48 half-hours.
    """
    records: list[dict] = []
    for index in range(48):
        if index == 10:
            continue  # entirely missing actual interval (05:00Z)
        start = _stamp(index * 30)
        publish = _stamp(index * 30 + 30)
        records.append(
            {
                "dataset": "FUELHH",
                "publishTime": publish,
                "startTime": start,
                "settlementDate": "2026-01-15",
                "settlementPeriod": index + 1,
                "fuelType": "WIND",
                "generation": None if index == 16 else 400 + (index + 1),
            }
        )
    # A re-release (correction) for the 09:00Z interval published later; its
    # normal release would have publishTime 09:30Z, so 09:45Z wins the dedupe.
    records.append(
        {
            "dataset": "FUELHH",
            "publishTime": "2026-01-15T09:45:00Z",
            "startTime": "2026-01-15T09:00:00Z",
            "settlementDate": "2026-01-15",
            "settlementPeriod": 19,
            "fuelType": "WIND",
            "generation": 490,
        }
    )
    # A non-wind record that selectors must never leak into the series.
    records.append(
        {
            "dataset": "FUELHH",
            "publishTime": "2026-01-15T01:00:00Z",
            "startTime": "2026-01-15T00:30:00Z",
            "settlementDate": "2026-01-15",
            "settlementPeriod": 3,
            "fuelType": "CCGT",
            "generation": 99999,
        }
    )
    return records


def synthetic_forecast_records() -> list[dict]:
    """WINDFOR records for a handful of delivery hours across the day.

    hour_end label T governs [T-1h, T):
      * 01:00Z: published 2026-01-14T09:30 (f=900), 15:00 (f=1000), next day 04:30 (f=1100)
      * 02:00Z: only published AFTER the day-ahead cutoff (f=800)
      * 03:00Z: no forecasts at all for that delivery hour
      * 13:00Z: an exact duplicate key (publishTime, startTime) twice, f=700/701 —
        the deterministic tie-break keeps the later source row.
      * 14:00Z: three vintages to exercise the explorer (500, 600, 650 all before cutoff)
    """
    records: list[dict] = []
    records.append({"dataset": "WINDFOR", "publishTime": "2026-01-14T09:30:00Z", "startTime": "2026-01-15T01:00:00Z", "generation": 900})
    records.append({"dataset": "WINDFOR", "publishTime": "2026-01-14T15:00:00Z", "startTime": "2026-01-15T01:00:00Z", "generation": 1000})
    records.append({"dataset": "WINDFOR", "publishTime": "2026-01-15T04:30:00Z", "startTime": "2026-01-15T01:00:00Z", "generation": 1100})
    records.append({"dataset": "WINDFOR", "publishTime": "2026-01-15T04:30:00Z", "startTime": "2026-01-15T02:00:00Z", "generation": 800})
    records.append({"dataset": "WINDFOR", "publishTime": "2026-01-14T02:30:00Z", "startTime": "2026-01-15T13:00:00Z", "generation": 700})
    records.append({"dataset": "WINDFOR", "publishTime": "2026-01-14T02:30:00Z", "startTime": "2026-01-15T13:00:00Z", "generation": 701})
    records.append({"dataset": "WINDFOR", "publishTime": "2026-01-14T02:30:00Z", "startTime": "2026-01-15T14:00:00Z", "generation": 500})
    records.append({"dataset": "WINDFOR", "publishTime": "2026-01-14T04:30:00Z", "startTime": "2026-01-15T14:00:00Z", "generation": 600})
    records.append({"dataset": "WINDFOR", "publishTime": "2026-01-14T07:30:00Z", "startTime": "2026-01-15T14:00:00Z", "generation": 650})
    records.append({"dataset": "WINDFOR", "publishTime": "2026-01-14T09:30:00Z", "startTime": "2025-12-25T12:00:00Z", "generation": 300})  # other-day hour
    return records


def write_synthetic_snapshot(base: Path) -> Path:
    snapshot_dir = base / "snapshot"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "fuelhh_wind.json").write_text(json.dumps(synthetic_actual_records()))
    (snapshot_dir / "windfor.json").write_text(json.dumps(synthetic_forecast_records()))
    (snapshot_dir / "manifest.json").write_text(
        json.dumps(
            {
                "source": "synthetic test fixture",
                "retrieved_at_utc": "2026-10-23T00:00:00Z",
                "period": {"settlement_from": "2026-01-15", "settlement_to": "2026-01-15"},
                "counts": {},
                "processing": ["fixture"],
                "alignment_convention": "hour-ending",
                "cutoff_assumption": {"default_preset": "day_ahead_1030"},
                "notes": [],
            }
        )
    )
    return snapshot_dir
