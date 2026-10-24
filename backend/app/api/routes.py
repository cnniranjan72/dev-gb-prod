from __future__ import annotations

import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from ..schemas import dtos
from ..services import accuracy, vintage
from ..services.conventions import hour_end_label, iso_london, iso_utc, settlement_date_local
from ..services.dataset import settlement_period_local
from ..services.security import require_role
from .state import get_dataset

logger = logging.getLogger("windlens.api")

router = APIRouter(prefix="/api")


def _parse_date(value: str, name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid {name}: expected YYYY-MM-DD, got {value!r}") from exc


def _cutoff_policy(preset: str | None, cutoff_iso: str | None):
    explicit = cutoff_iso if cutoff_iso else None
    chosen = preset or "day_ahead_1030"
    if explicit is None and chosen == "custom":
        raise HTTPException(status_code=400, detail="custom cutoff requires 'cutoff' ISO datetime parameter")
    try:
        policy = accuracy.CutoffPolicy.from_params(chosen, explicit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return policy


def _dataset_for_date(delivery_date: date):
    dataset = get_dataset()
    if dataset.actuals and not (
        dataset.coverage_start_date <= delivery_date <= dataset.coverage_end_date
    ):
        raise HTTPException(
            status_code=404,
            detail=f"delivery date {delivery_date.isoformat()} outside dataset coverage "
            f"({dataset.period_start.date().isoformat()}..{dataset.period_end.date().isoformat()})",
        )
    return dataset


@router.get("/health", response_model=dtos.HealthResponse)
def health() -> dtos.HealthResponse:
    from ..core.config import settings

    dataset = get_dataset()
    return dtos.HealthResponse(
        status="ok",
        version=settings.version,
        data_mode=dataset.snapshot_metadata.get("mode", settings.data_mode),
        dataset_start_utc=iso_utc(dataset.period_start) if dataset.actuals else None,
        dataset_end_utc=iso_utc(dataset.period_end) if dataset.actuals else None,
        actual_rows=len(dataset.actuals),
        forecast_rows=sum(len(v) for v in dataset.forecasts_by_hour_end.values()),
    )


@router.get("/metadata", response_model=dtos.SnapshotManifestResponse)
def metadata(session: object = Depends(require_role("viewer"))) -> dtos.SnapshotManifestResponse:
    meta = get_dataset().snapshot_metadata
    return dtos.SnapshotManifestResponse(
        source=meta.get("source", ""),
        retrieved_at_utc=meta.get("retrieved_at_utc"),
        period=meta.get("period", {}),
        counts=meta.get("counts", {}),
        processing=meta.get("processing", []),
        alignment_convention=meta.get("alignment_convention", ""),
        cutoff_assumption=meta.get("cutoff_assumption", {}),
        notes=meta.get("notes", []),
    )


@router.get("/summary", response_model=dtos.SummaryResponse)
def summary(
    _viewer: object = Depends(require_role("viewer")),
    date: str = Query(..., description="GB delivery date YYYY-MM-DD"),
    preset: str = Query("day_ahead_1030", description="cutoff preset id or 'custom'"),
    cutoff: str | None = Query(None, description="explicit ISO-8601 UTC cutoff; overrides preset"),
) -> dtos.SummaryResponse:
    delivery_date = _parse_date(date, "date")
    dataset = _dataset_for_date(delivery_date)
    policy = _cutoff_policy(preset, cutoff)
    points = dataset.compute_interval_points(delivery_date, accuracy.cutoff_for_day(delivery_date, policy))
    return dtos.SummaryResponse(
        delivery_date=delivery_date.isoformat(),
        cutoff=dtos.CutoffDescriptor(**policy.describe(delivery_date)),
        metrics=dtos.MetricSummary(**accuracy.summary_metrics(points).to_dict()),
        coverage=dtos.CoverageResponse(**accuracy.coverage(points).to_dict()),
    )


@router.get("/series", response_model=dtos.SeriesResponse)
def series(
    _viewer: object = Depends(require_role("viewer")),
    date: str = Query(...),
    preset: str = Query("day_ahead_1030"),
    cutoff: str | None = Query(None),
) -> dtos.SeriesResponse:
    delivery_date = _parse_date(date, "date")
    dataset = _dataset_for_date(delivery_date)
    policy = _cutoff_policy(preset, cutoff)
    cutoff_utc = accuracy.cutoff_for_day(delivery_date, policy)
    points = dataset.compute_interval_points(delivery_date, cutoff_utc)
    serialised = []
    for point in points:
        publish = point.forecast_publish_time
        serialised.append(
            dtos.SeriesPoint(
                interval_start_utc=iso_utc(point.interval_start),
                interval_start_london=iso_london(point.interval_start),
                settlement_date=point.settlement_date.isoformat(),
                settlement_period=point.settlement_period,
                actual_mw=point.actual_mw,
                forecast_mw=point.forecast_mw,
                forecast_publish_time_utc=iso_utc(publish) if publish else None,
                forecast_publish_time_london=iso_london(publish) if publish else None,
                available=point.available,
                error_mw=point.error_mw,
            )
        )
    return dtos.SeriesResponse(
        delivery_date=delivery_date.isoformat(),
        cutoff=dtos.CutoffDescriptor(**policy.describe(delivery_date)),
        points=serialised,
    )


@router.get("/vintages", response_model=dtos.VintagesResponse)
def vintages(
    _analyst: object = Depends(require_role("analyst")),
    date: str = Query(...),
    period: int = Query(..., ge=1, le=50, description="1-based GB settlement period"),
    preset: str = Query("day_ahead_1030"),
    cutoff: str | None = Query(None),
) -> dtos.VintagesResponse:
    delivery_date = _parse_date(date, "date")
    dataset = _dataset_for_date(delivery_date)
    policy = _cutoff_policy(preset, cutoff)
    cutoff_utc = accuracy.cutoff_for_day(delivery_date, policy)
    starts = dataset.delivery_date_interval_starts(delivery_date)
    matches = [s for s in starts if settlement_period_local(s) == period]
    if not matches:
        raise HTTPException(status_code=404, detail=f"no interval with period {period} on {delivery_date}")
    interval_start = matches[0]
    hour_end = hour_end_label(interval_start)
    evaluations = vintage.evaluate_vintages(dataset.vintage_candidates(hour_end), hour_end, cutoff_utc)
    return dtos.VintagesResponse(
        settlement_date=delivery_date.isoformat(),
        settlement_period=period,
        interval_start_utc=iso_utc(interval_start),
        hour_end_label_utc=iso_utc(hour_end),
        cutoff=dtos.CutoffDescriptor(**policy.describe(delivery_date)),
        selected_forecast_mw=next((v.generation_mw for v in evaluations if v.selected), None),
        available=any(v.selected for v in evaluations),
        vintages=[
            dtos.VintageRecord(
                publish_time_utc=iso_utc(v.publish_time),
                publish_time_london=iso_london(v.publish_time),
                forecast_mw=v.generation_mw,
                lead_hours=round(v.lead_hours, 2),
                eligible=v.eligible,
                excluded_reason=v.excluded_reason,
                selected=v.selected,
            )
            for v in evaluations
        ],
    )


@router.get("/accuracy", response_model=dtos.AccuracyResponse)
def accuracy_endpoint(
    _analyst: object = Depends(require_role("analyst")),
    preset: str = Query("day_ahead_1030"),
    cutoff: str | None = Query(None),
) -> dtos.AccuracyResponse:
    dataset = get_dataset()
    policy = _cutoff_policy(preset, cutoff)
    start_date = dataset.coverage_start_date
    end_date = dataset.coverage_end_date
    all_points: list = []
    daily_rows: list[dtos.DailyErrorRow] = []
    day = start_date
    while day <= end_date:
        cutoff_utc = accuracy.cutoff_for_day(day, policy)
        points = dataset.compute_interval_points(day, cutoff_utc)
        all_points.extend(points)
        daily_rows.append(
            dtos.DailyErrorRow(
                delivery_date=day.isoformat(),
                cutoff_utc=iso_utc(cutoff_utc),
                metrics=dtos.MetricSummary(**accuracy.summary_metrics(points).to_dict()),
            )
        )
        day += timedelta(days=1)
    overall = accuracy.summary_metrics(all_points)
    histogram = accuracy.histogram(all_points)
    hour_rows = accuracy.by_london_hour(all_points)
    return dtos.AccuracyResponse(
        period_start_date=start_date.isoformat(),
        period_end_date=end_date.isoformat(),
        cutoff=dtos.CutoffDescriptor(**policy.describe(start_date)),
        overall=dtos.MetricSummary(**overall.to_dict()),
        by_day=daily_rows,
        by_london_hour=[
            dtos.HourOfDayRow(
                london_hour=row["london_hour"],
                count=row["count"],
                mae_mw=row["mae_mw"],
                rmse_mw=row["rmse_mw"],
                mean_bias_mw=row["mean_bias_mw"],
            )
            for row in hour_rows
        ],
        error_histogram=histogram,
    )
