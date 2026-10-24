from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .conventions import LONDON, iso_utc, settlement_date_local, to_utc
from .dataset import ForecastDataset, IntervalPoint
from .metrics import ErrorHistogramBin, MetricsResult, compute_metrics, error_histogram
from .vintage import CUTOFF_PRESETS, DEFAULT_CUTOFF_PRESET, decision_cutoff_utc


def error_of(point: IntervalPoint) -> float | None:
    if point.forecast_mw is None or point.actual_mw is None:
        return None
    return point.forecast_mw - point.actual_mw


@dataclass(frozen=True)
class CutoffPolicy:
    """Per-interval procurement decision-cutoff resolution.

    preset mode: cutoff is anchored to each interval's GB delivery day
    (configured clock time before London midnight). custom mode: one fixed
    UTC instant applies to every interval of the query — clearly an analytical
    lens, surfaced in the UI and docs.
    """
    preset: str = DEFAULT_CUTOFF_PRESET
    custom_iso: str | None = None

    @classmethod
    def from_params(cls, preset: str, explicit_iso: str | None) -> "CutoffPolicy":
        if explicit_iso:
            to_utc(explicit_iso)  # validation before construction
            return cls(preset="custom", custom_iso=explicit_iso)
        if preset not in CUTOFF_PRESETS:
            raise ValueError(f"unknown cutoff preset: {preset}")
        return cls(preset=preset, custom_iso=None)

    def for_interval(self, interval_start: datetime) -> datetime:
        if self.custom_iso:
            return to_utc(self.custom_iso)
        return decision_cutoff_utc(settlement_date_local(interval_start), self.preset)

    def describe(self, delivery_date: date) -> dict:
        from .conventions import iso_london

        if self.custom_iso:
            cutoff = to_utc(self.custom_iso)
            return {"mode": "custom", "preset": None, "cutoff_utc": iso_utc(cutoff), "cutoff_london": iso_london(cutoff)}
        cutoff = decision_cutoff_utc(delivery_date, self.preset)
        return {
            "mode": "preset",
            "preset": self.preset,
            "cutoff_utc": iso_utc(cutoff),
            "cutoff_london": iso_london(cutoff),
        }


@dataclass(frozen=True)
class CoverageStats:
    expected_intervals: int
    intervals_with_actual: int
    intervals_with_selected_forecast: int
    valid_pairs: int
    missing_actual_intervals: int
    missing_forecast_intervals: int

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def coverage(points: list[IntervalPoint]) -> CoverageStats:
    with_actual = sum(1 for p in points if p.actual_mw is not None)
    with_forecast = sum(1 for p in points if p.forecast_mw is not None)
    valid = sum(1 for p in points if error_of(p) is not None)
    n = len(points)
    return CoverageStats(
        expected_intervals=n,
        intervals_with_actual=with_actual,
        intervals_with_selected_forecast=with_forecast,
        valid_pairs=valid,
        missing_actual_intervals=n - with_actual,
        missing_forecast_intervals=n - with_forecast,
    )


def summary_metrics(points: list[IntervalPoint]) -> MetricsResult:
    return compute_metrics([(p.forecast_mw, p.actual_mw) for p in points])


def cutoff_for_day(dataset_day: date, policy: CutoffPolicy) -> datetime:
    if policy.custom_iso:
        return to_utc(policy.custom_iso)
    return decision_cutoff_utc(dataset_day, policy.preset)


def daily_breakdown(
    dataset: ForecastDataset,
    start_date: date,
    end_date: date,
    policy: CutoffPolicy,
) -> list[dict]:
    rows: list[dict] = []
    day = start_date
    while day <= end_date:
        cutoff = cutoff_for_day(day, policy)
        points = dataset.compute_interval_points(day, cutoff)
        metrics = summary_metrics(points)
        rows.append(
            {
                "delivery_date": day.isoformat(),
                "cutoff_utc": iso_utc(cutoff),
                "metrics": metrics.to_dict(),
            }
        )
        day += timedelta(days=1)
    return rows


def by_london_hour(points: list[IntervalPoint]) -> list[dict]:
    buckets: dict[int, list[float]] = {}
    for point in points:
        error = error_of(point)
        if error is None:
            continue
        hour = point.interval_start.astimezone(LONDON).hour
        buckets.setdefault(hour, []).append(error)
    rows: list[dict] = []
    for hour in sorted(buckets):
        metrics = compute_metrics([(e, 0.0) for e in buckets[hour]])
        rows.append({"london_hour": hour, **metrics.to_dict()})
    return rows


def histogram(points: list[IntervalPoint]) -> list[dict]:
    errors = [e for e in (error_of(p) for p in points) if e is not None]
    bins: list[ErrorHistogramBin] = error_histogram(errors)
    return [{"lower_mw": b.lower_mw, "upper_mw": b.upper_mw, "count": b.count} for b in bins]
