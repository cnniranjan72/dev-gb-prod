from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.conventions import (
    hour_end_label,
    iso_utc,
    settlement_date_local,
    to_utc,
)
from app.services.loader import (
    ActualRow,
    ForecastRow,
    dedupe_actuals,
    dedupe_forecasts,
    normalize_actuals,
    normalize_forecasts,
)


UTC = timezone.utc


def test_to_utc_handles_z_and_naive():
    assert iso_utc("2026-01-14T10:30:00Z") == "2026-01-14T10:30:00Z"
    naive = datetime(2026, 1, 14, 10, 30)
    assert to_utc(naive).tzinfo == UTC
    assert to_utc(naive).astimezone(UTC).isoformat().endswith("+00:00")


def test_settlement_date_local_gmt_january():
    assert settlement_date_local("2026-01-15T10:00:00Z").isoformat() == "2026-01-15"


def test_settlement_date_local_bst_2330z_rolls_to_next_day():
    assert settlement_date_local("2025-10-22T23:30:00Z").isoformat() == "2025-10-23"


def test_hour_end_label_maps_half_hour_to_containing_hour_end():
    assert iso_utc(hour_end_label(to_utc("2026-01-15T00:30:00Z"))) == "2026-01-15T01:00:00Z"
    assert iso_utc(hour_end_label(to_utc("2026-01-15T08:00:00Z"))) == "2026-01-15T09:00:00Z"


def test_normalize_actuals_filters_to_wind_only():
    records = [
        {"startTime": "2026-01-15T00:00:00Z", "publishTime": "2026-01-15T00:30:00Z", "fuelType": "WIND", "generation": 8500},
        {"startTime": "2026-01-15T00:00:00Z", "publishTime": "2026-01-15T00:30:00Z", "fuelType": "CCGT", "generation": 400},
        {"startTime": "2026-01-15T00:30:00Z", "publishTime": "2026-01-15T01:00:00Z", "fuelType": "WIND", "generation": "9100"},
        {"startTime": "2026-01-15T01:00:00Z", "publishTime": "2026-01-15T01:30:00Z", "fuelType": "WIND", "generation": None},
        {"startTime": "2026-01-15T01:30:00Z", "publishTime": "2026-01-15T02:00:00Z", "fuelType": "WIND", "generation": "not-a-number"},
    ]
    rows = normalize_actuals(records)
    assert len(rows) == 4  # CCGG filtered out &WIND only
    assert [r.generation_mw for r in rows] == [8500.0, 9100.0, None, None]


def test_missing_generation_never_becomes_zero():
    rows = normalize_actuals(
        [{"startTime": "2026-01-15T01:00:00Z", "publishTime": "2026-01-15T01:30:00Z", "fuelType": "WIND", "generation": None}]
    )
    assert rows[0].generation_mw is None


def test_dedupe_actuals_latest_publish_wins():
    first = ActualRow(to_utc("2026-01-15T09:00:00Z"), None, 419, to_utc("2026-01-15T09:30:00Z"))
    second = ActualRow(to_utc("2026-01-15T09:00:00Z"), None, 490, to_utc("2026-01-15T09:45:00Z"))
    merged = dedupe_actuals([first, second])
    assert merged[0].generation_mw == 490


def test_dedupe_forecasts_exact_duplicate_keeps_later_source_order():
    rows = [
        ForecastRow(to_utc("2026-01-15T13:00:00Z"), to_utc("2026-01-14T02:30:00Z"), 700, 0),
        ForecastRow(to_utc("2026-01-15T13:00:00Z"), to_utc("2026-01-14T02:30:00Z"), 701, 1),
    ]
    merged = dedupe_forecasts(rows)
    assert len(merged) == 1
    assert merged[0].generation_mw == 701


def test_dedupe_forecasts_keeps_distinct_vintages():
    rows = normalize_forecasts(
        [
            {"publishTime": "2026-01-14T02:30:00Z", "startTime": "2026-01-15T13:00:00Z", "generation": 700},
            {"publishTime": "2026-01-14T04:30:00Z", "startTime": "2026-01-15T13:00:00Z", "generation": 701},
        ]
    )
    assert len(dedupe_forecasts(rows)) == 2
