from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.conventions import hour_end_label, to_utc
from app.services.loader import ForecastRow, normalize_forecasts
from app.services.vintage import (
    CUTOFF_PRESETS,
    DEFAULT_CUTOFF_PRESET,
    decision_cutoff_utc,
    evaluate_vintages,
    select_forecast,
)

UTC = timezone.utc


def row(publish: str, hour_end: str, mw: float | None, index: int = 0) -> ForecastRow:
    return ForecastRow(hour_end=to_utc(hour_end), publish_time=to_utc(publish), generation_mw=mw, row_index=index)


# GB delivery 2026-01-15 with day_ahead_1030 preset -> cutoff 2026-01-14T10:30Z
CUTOFF = decision_cutoff_utc(datetime(2026, 1, 15).date(), "day_ahead_1030")


def test_cutoff_preset_resolves_to_verified_market_schedule():
    assert CUTOFF == datetime(2026, 1, 14, 10, 30, tzinfo=UTC)


def test_gate_preset_matches_0950_n2ex_close():
    gate = decision_cutoff_utc(datetime(2026, 1, 15).date(), "day_ahead_gate_0950")
    assert gate == datetime(2026, 1, 14, 9, 50, tzinfo=UTC)


def test_select_forecast_picks_latest_eligible():
    vintages = [
        row("2026-01-14T09:30:00Z", "2026-01-15T01:00:00Z", 900, 0),
        row("2026-01-14T15:00:00Z", "2026-01-15T01:00:00Z", 1000, 1),
        row("2026-01-15T04:30:00Z", "2026-01-15T01:00:00Z", 1100, 2),
    ]
    winner = select_forecast(vintages, to_utc("2026-01-15T01:00:00Z"), CUTOFF)
    assert winner is not None
    assert winner.generation_mw == 900  # only the pre-cutoff record is selectable


def test_post_cutoff_forecast_never_selected_even_when_only_record():
    vintages = [row("2026-01-15T04:30:00Z", "2026-01-15T02:00:00Z", 800, 0)]
    assert select_forecast(vintages, to_utc("2026-01-15T02:00:00Z"), CUTOFF) is None


def test_no_eligible_forecast_returns_explicit_unavailable():
    assert select_forecast([], to_utc("2026-01-15T03:00:00Z"), CUTOFF) is None


def test_selection_is_deterministic_on_publish_tie():
    vintages = [
        row("2026-01-14T02:30:00Z", "2026-01-15T13:00:00Z", 700, 0),
        row("2026-01-14T02:30:00Z", "2026-01-15T13:00:00Z", 701, 1),
    ]
    winner = select_forecast(vintages, to_utc("2026-01-15T13:00:00Z"), CUTOFF)
    assert winner.generation_mw == 701


def test_cutoff_inclusive_at_boundary():
    vintages = [row("2026-01-14T10:30:00Z", "2026-01-15T01:00:00Z", 850, 0)]
    assert select_forecast(vintages, to_utc("2026-01-15T01:00:00Z"), CUTOFF).generation_mw == 850


def test_hour_end_scope_isolates_other_delivery_hours():
    vintages = [
        row("2026-01-14T09:30:00Z", "2026-01-15T01:00:00Z", 900, 0),
        row("2026-01-14T09:30:00Z", "2025-12-25T12:00:00Z", 300, 1),
    ]
    assert select_forecast(vintages, to_utc("2026-01-15T01:00:00Z"), CUTOFF).generation_mw == 900


def test_evaluate_vintages_marks_eligibility_and_winner():
    records = [
        {"publishTime": "2026-01-14T02:30:00Z", "startTime": "2026-01-15T14:00:00Z", "generation": 500},
        {"publishTime": "2026-01-14T04:30:00Z", "startTime": "2026-01-15T14:00:00Z", "generation": 600},
        {"publishTime": "2026-01-14T07:30:00Z", "startTime": "2026-01-15T14:00:00Z", "generation": 650},
        {"publishTime": "2026-01-14T12:30:00Z", "startTime": "2026-01-15T14:00:00Z", "generation": 660},
    ]
    vintages = normalize_forecasts(records)
    evaluations = evaluate_vintages(vintages, to_utc("2026-01-15T14:00:00Z"), CUTOFF)
    by_publish = {e.publish_time.isoformat(): e for e in evaluations}
    after = by_publish["2026-01-14T12:30:00+00:00"]
    assert after.eligible is False
    assert after.excluded_reason == "after_cutoff"
    assert by_publish["2026-01-14T07:30:00+00:00"].selected is True
    assert by_publish["2026-01-14T02:30:00+00:00"].eligible is True
    assert by_publish["2026-01-14T02:30:00+00:00"].selected is False


def test_default_preset_is_day_ahead_1030():
    assert DEFAULT_CUTOFF_PRESET == "day_ahead_1030"
    assert "day_ahead_1030" in CUTOFF_PRESETS


def test_custom_cutoff_validation_rejects_unknown_preset():
    import pytest as _pytest

    from app.services.vintage import resolve_cutoff

    with _pytest.raises(ValueError):
        resolve_cutoff(datetime(2026, 1, 15).date(), preset="does_not_exist")
    with _pytest.raises(ValueError):
        resolve_cutoff(None)  # no date, no explicit cutoff
