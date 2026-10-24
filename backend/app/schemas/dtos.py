from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    version: str
    data_mode: str
    dataset_start_utc: str | None
    dataset_end_utc: str | None
    actual_rows: int
    forecast_rows: int


class CutoffDescriptor(BaseModel):
    mode: str
    preset: str | None = None
    cutoff_utc: str
    cutoff_london: str


class MetricSummary(BaseModel):
    count: int
    mae_mw: float | None = None
    rmse_mw: float | None = None
    mean_bias_mw: float | None = None


class CoverageResponse(BaseModel):
    expected_intervals: int
    intervals_with_actual: int
    intervals_with_selected_forecast: int
    valid_pairs: int
    missing_actual_intervals: int
    missing_forecast_intervals: int


class SummaryResponse(BaseModel):
    delivery_date: str
    cutoff: CutoffDescriptor
    metrics: MetricSummary
    coverage: CoverageResponse


class SeriesPoint(BaseModel):
    interval_start_utc: str
    interval_start_london: str
    settlement_date: str
    settlement_period: int
    actual_mw: float | None
    forecast_mw: float | None
    forecast_publish_time_utc: str | None
    forecast_publish_time_london: str | None
    available: bool
    error_mw: float | None


class SeriesResponse(BaseModel):
    delivery_date: str
    cutoff: CutoffDescriptor
    points: list[SeriesPoint]


class VintageRecord(BaseModel):
    publish_time_utc: str
    publish_time_london: str
    forecast_mw: float | None
    lead_hours: float
    eligible: bool
    excluded_reason: str | None = None
    selected: bool


class VintagesResponse(BaseModel):
    settlement_date: str
    settlement_period: int
    interval_start_utc: str
    hour_end_label_utc: str
    cutoff: CutoffDescriptor
    selected_forecast_mw: float | None = None
    available: bool
    vintages: list[VintageRecord]


class DailyErrorRow(BaseModel):
    delivery_date: str
    cutoff_utc: str
    metrics: MetricSummary


class HourOfDayRow(BaseModel):
    london_hour: int
    count: int
    mae_mw: float | None = None
    rmse_mw: float | None = None
    mean_bias_mw: float | None = None


class AccuracyResponse(BaseModel):
    period_start_date: str
    period_end_date: str
    cutoff: CutoffDescriptor
    overall: MetricSummary
    by_day: list[DailyErrorRow]
    by_london_hour: list[HourOfDayRow]
    error_histogram: list[dict[str, Any]] = Field(default_factory=list)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    email: str
    role: str


class UserOut(BaseModel):
    email: str
    role: str


class SnapshotManifestResponse(BaseModel):
    source: str
    retrieved_at_utc: str | None
    period: dict[str, Any]
    counts: dict[str, Any]
    processing: list[str]
    alignment_convention: str
    cutoff_assumption: dict[str, Any]
    notes: list[str]
