from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from .conventions import (
    LONDON,
    hour_end_label,
    london_date_to_utc_window,
    settlement_date_local,
    to_utc,
)
from .loader import (
    ActualRow,
    ForecastRow,
    dedupe_actuals,
    dedupe_forecasts,
    normalize_actuals,
    normalize_forecasts,
)
from .vintage import select_forecast


def settlement_period_local(interval_start: datetime) -> int:
    """1-based half-hour index within the GB settlement day, from London time.

    Verified against live payloads: 23:00Z in BST -> period 1 of the next
    settlement day; 11:30Z in GMT -> period 24 of the same day. (January's
    range contains no clock transition; the formula is kept general.)
    """
    local = to_utc(interval_start).astimezone(LONDON)
    return local.hour * 2 + local.minute // 30 + 1


@dataclass(frozen=True)
class IntervalPoint:
    interval_start: datetime
    settlement_date: date
    settlement_period: int
    actual_mw: object | None
    forecast_mw: object | None
    forecast_publish_time: object | None
    available: bool

    @property
    def error_mw(self) -> object | None:
        if self.forecast_mw is None or self.actual_mw is None:
            return None
        return self.forecast_mw - self.actual_mw


@dataclass(frozen=True)
class ForecastDataset:
    actuals: dict[datetime, ActualRow]
    forecasts_by_hour_end: dict[datetime, list[ForecastRow]]
    period_start: datetime
    period_end: datetime
    coverage_start_date: date
    coverage_end_date: date
    snapshot_metadata: dict

    @classmethod
    def from_records(
        cls,
        actual_records: list[dict],
        forecast_records: list[dict],
        snapshot_metadata: dict | None = None,
    ) -> "ForecastDataset":
        actuals = {row.interval_start: row for row in dedupe_actuals(normalize_actuals(actual_records))}
        forecasts = dedupe_forecasts(normalize_forecasts(forecast_records))
        by_hour: dict[datetime, list[ForecastRow]] = {}
        for row in forecasts:
            bucket = by_hour.setdefault(row.hour_end, [])
            bucket.append(row)
        if actuals:
            period_start = min(actuals)
            period_end = max(actuals) + timedelta(minutes=30)
            coverage_start_date = settlement_date_local(period_start)
            coverage_end_date = settlement_date_local(max(actuals))
        else:
            period_start = period_end = to_utc("1970-01-01T00:00Z")
            coverage_start_date = coverage_end_date = date(1970, 1, 1)
        return cls(
            actuals=actuals,
            forecasts_by_hour_end=by_hour,
            period_start=period_start,
            period_end=period_end,
            coverage_start_date=coverage_start_date,
            coverage_end_date=coverage_end_date,
            snapshot_metadata=snapshot_metadata or {},
        )

    @classmethod
    def from_snapshot(cls, snapshot_dir: str | Path) -> "ForecastDataset":
        path = Path(snapshot_dir)
        actuals = json.loads((path / "fuelhh_wind.json").read_text(encoding="utf-8"))
        windfor = json.loads((path / "windfor.json").read_text(encoding="utf-8"))
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        return cls.from_records(actuals, windfor, manifest)

    def delivery_date_interval_starts(self, delivery_date: date) -> list[datetime]:
        start_utc, end_utc = london_date_to_utc_window(delivery_date)
        starts: list[datetime] = []
        cursor = start_utc
        while cursor < end_utc:
            starts.append(cursor)
            cursor += timedelta(minutes=30)
        return starts

    def actual_for(self, interval_start: datetime) -> ActualRow | None:
        return self.actuals.get(interval_start)

    def vintage_candidates(self, hour_end: datetime) -> list[ForecastRow]:
        return self.forecasts_by_hour_end.get(hour_end, [])

    def compute_interval_points(self, delivery_date: date, cutoff: datetime) -> list[IntervalPoint]:
        points: list[IntervalPoint] = []
        for interval_start in self.delivery_date_interval_starts(delivery_date):
            actual = self.actuals.get(interval_start)
            hour_end = hour_end_label(interval_start)
            forecast = select_forecast(self.vintage_candidates(hour_end), hour_end, cutoff)
            points.append(
                IntervalPoint(
                    interval_start=interval_start,
                    settlement_date=settlement_date_local(interval_start),
                    settlement_period=settlement_period_local(interval_start),
                    actual_mw=actual.generation_mw if actual else None,
                    forecast_mw=forecast.generation_mw if forecast else None,
                    forecast_publish_time=forecast.publish_time if forecast else None,
                    available=forecast is not None,
                )
            )
        return points
