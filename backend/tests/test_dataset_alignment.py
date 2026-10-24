from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.services.accuracy import CutoffPolicy, coverage, cutoff_for_day, summary_metrics
from app.services.conventions import iso_utc, settlement_date_local, to_utc
from app.services.dataset import ForecastDataset, settlement_period_local
from app.services.vintage import decision_cutoff_utc
from tests.fixtures import write_synthetic_snapshot

UTC = timezone.utc


@pytest.fixture(scope="module")
def dataset(tmp_path_factory) -> ForecastDataset:
    path = write_synthetic_snapshot(tmp_path_factory.mktemp("snap"))
    return ForecastDataset.from_snapshot(path)


def test_delivery_day_spawns_48_half_hours(dataset):
    starts = dataset.delivery_date_interval_starts(date(2026, 1, 15))
    assert len(starts) == 48
    assert iso_utc(starts[0]) == "2026-01-15T00:00:00Z"
    assert iso_utc(starts[47]) == "2026-01-15T23:30:00Z"


def test_settlement_period_local_matches_elexon_convention():
    assert settlement_period_local(to_utc("2026-01-15T00:00:00Z")) == 1
    assert settlement_period_local(to_utc("2026-01-15T23:30:00Z")) == 48
    assert settlement_period_local(to_utc("2026-01-15T11:30:00Z")) == 24


def test_missing_actual_stays_missing_not_zero(dataset):
    policy = CutoffPolicy()
    points = dataset.compute_interval_points(date(2026, 1, 15), cutoff_for_day(date(2026, 1, 15), policy))
    period10 = points[10]  # interval 05:00Z, deliberately absent
    period16 = points[16]  # interval 08:00Z, generation null in source
    assert period10.actual_mw is None
    assert period16.actual_mw is None


def test_actual_re_release_wins(dataset):
    policy = CutoffPolicy()
    points = dataset.compute_interval_points(date(2026, 1, 15), cutoff_for_day(date(2026, 1, 15), policy))
    period19 = points[18]  # 09:00Z interval
    assert period19.actual_mw == 490.0


def test_selected_forecasts_follow_cutoff(dataset):
    policy = CutoffPolicy()
    cutoff = cutoff_for_day(date(2026, 1, 15), policy)
    points = dataset.compute_interval_points(date(2026, 1, 15), cutoff)

    # periods 1 & 2 (00:00 / 00:30) -> hour_end 01:00Z -> 900 selected at 10:30 cutoff
    assert points[0].available and points[0].forecast_mw == 900.0
    assert points[0].forecast_publish_time == to_utc("2026-01-14T09:30:00Z")
    assert points[1].forecast_mw == 900.0
    # periods 3 & 4 (01:00 / 01:30) -> hour_end 02:00Z: only post-cutoff vintage exists
    assert points[2].available is False and points[2].forecast_mw is None
    # hour_end 03:00Z: no forecast rows at all
    assert points[4].available is False
    # hour_end 13:00Z duplicate-tie-break: later source row (701)
    assert points[24].forecast_mw == 701.0
    # hour_end 14:00Z three pre-cutoff vintages => latest eligible (07:30 publish / 650)
    assert points[26].forecast_mw == 650.0


def test_custom_fixed_cutoff_applies_dataset_wide(dataset):
    policy = CutoffPolicy(preset="custom", custom_iso="2026-01-14T15:00:00Z")
    cutoff = cutoff_for_day(date(2026, 1, 15), policy)
    points = dataset.compute_interval_points(date(2026, 1, 15), cutoff)
    assert points[0].forecast_mw == 1000.0  # publish exactly == cutoff is eligible (inclusive boundary)
    assert points[2].available is False  # 04:30Z publish is _after_ the new cutoff


def test_later_cutoff_upgrades_selection(dataset):
    early = dataset.compute_interval_points(
        date(2026, 1, 15), decision_cutoff_utc(date(2026, 1, 15), "day_ahead_1030")
    )
    late = dataset.compute_interval_points(
        date(2026, 1, 15), decision_cutoff_utc(date(2026, 1, 15), "intraday_auction_1730")
    )
    assert early[0].forecast_publish_time == to_utc("2026-01-14T09:30:00Z")
    assert late[0].forecast_publish_time == to_utc("2026-01-14T15:00:00Z")
    assert late[0].forecast_mw == 1000.0


def test_summary_metrics_only_from_valid_pairs(dataset):
    policy = CutoffPolicy()
    cutoff = cutoff_for_day(date(2026, 1, 15), policy)
    points = dataset.compute_interval_points(date(2026, 1, 15), cutoff)
    summary = summary_metrics(points)
    stats = coverage(points)
    assert stats.expected_intervals == 48
    assert stats.intervals_with_actual == 46  # 1 absent + 1 null
    assert stats.intervals_with_selected_forecast == 6  # hours 01:00Z,13:00Z,14:00Z only
    assert stats.valid_pairs == 6
    assert summary.count == stats.valid_pairs
