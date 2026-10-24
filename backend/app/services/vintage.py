from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .conventions import LONDON, hour_end_label, to_utc
from .loader import ForecastRow

# Decision-cutoff presets. Verified market anchor: the N2EX day-ahead auction
# gate closes 09:50 GMT on D-1 and results publish by 10:00 GMT (Nord Pool
# documentation; regime in force since GB left EU day-ahead coupling on
# 2021-01-01). Each preset is expressed as the exact offset BEFORE London
# midnight of the delivery day and computed in Europe/London, so the instant
# shifts correctly across BST/GMT transitions.
CUTOFF_PRESETS: dict[str, dict[str, str]] = {
    # Delivery-day London clock time 10:30 => 13h30m before London midnight.
    "day_ahead_1030": "13:30",
    # Delivery-day London clock time 09:50 => 14h10m before London midnight.
    "day_ahead_gate_0950": "14:10",
    # Delivery-day London clock time 17:30 => 6h30m before London midnight.
    "intraday_auction_1730": "06:30",
}

DEFAULT_CUTOFF_PRESET = "day_ahead_1030"


def parse_anchored_time(spec: str) -> timedelta:
    hours_text, _, minutes_text = spec.partition(":")
    return timedelta(hours=int(hours_text), minutes=int(minutes_text))


def decision_cutoff_utc(delivery_date: date, preset: str = DEFAULT_CUTOFF_PRESET) -> datetime:
    """UTC instant of the procurement decision cutoff for a GB delivery day.

    This is an analytical assumption, made explicit in UI/docs: the customer's
    day-ahead purchase is treated as finalised after DA auction results become
    public. Configure through `preset` or an explicit ISO cutoff.
    """
    if preset not in CUTOFF_PRESETS:
        raise ValueError(f"unknown cutoff preset: {preset if preset else 'None'}")
    midnight_local = datetime(delivery_date.year, delivery_date.month, delivery_date.day, tzinfo=LONDON)
    return midnight_local - parse_anchored_time(CUTOFF_PRESETS[preset])


def resolve_cutoff(
    delivery_date: date | None,
    preset: str = DEFAULT_CUTOFF_PRESET,
    explicit_iso: str | None = None,
) -> tuple[datetime, str]:
    """Resolve the cutoff to use: a fixed explicit ISO-UTC instant for the entire
    query (`custom`), or the day-anchored preset. Returns (cutoff, descriptor).
    """
    if explicit_iso:
        return to_utc(explicit_iso), "custom"
    if preset not in CUTOFF_PRESETS:
        raise ValueError(f"unknown cutoff preset: {preset}")
    if delivery_date is None:
        raise ValueError("a delivery date is required for preset cutoffs")
    return decision_cutoff_utc(delivery_date, preset), preset


@dataclass(frozen=True)
class VintageEvaluation:
    publish_time: object
    generation_mw: object
    lead_hours: object
    eligible: bool
    excluded_reason: str | None  # None | "after_cutoff"
    selected: bool = False


def select_forecast(
    vintages: list[ForecastRow],
    hour_end: datetime,
    cutoff: datetime,
) -> ForecastRow | None:
    """The cardinal historical forecast-vintage selection rule.

        winner = argmax publishTime over {publishTime <= cutoff}

    among records for the delivery hour labelled `hour_end` (under the resolved
    hour-ending convention this labels [T-1h, T)).

    Properties enforced and tested:
      * forecasts published after the cutoff are never used (no look-ahead bias);
      * never substitutes a latest/current forecast where no eligible one
        existed historically — returns None and the caller surfaces an
        explicit 'unavailable' instead;
      * deterministic on ties (greater source order wins);
      * tz-aware throughout.
    """
    eligible = [row for row in vintages if row.hour_end == hour_end and row.publish_time <= cutoff]
    if not eligible:
        return None
    return max(eligible, key=lambda row: (row.publish_time, row.row_index))


def evaluate_vintages(
    vintages: list[ForecastRow],
    hour_end: datetime,
    cutoff: datetime,
) -> list[VintageEvaluation]:
    """Per-record eligibility facts for the vintage-explorer UI plus the chosen
    winner marked `selected`. The list is published-priority descending."""
    rows = sorted(
        (row for row in vintages if row.hour_end == hour_end),
        key=lambda r: (r.publish_time, r.row_index),
    )
    winner = select_forecast(vintages, hour_end, cutoff)
    winner_key = None if winner is None else (winner.publish_time, winner.row_index)
    evaluations: list[VintageEvaluation] = []
    for row in rows:
        evaluations.append(
            VintageEvaluation(
                publish_time=row.publish_time,
                generation_mw=row.generation_mw,
                lead_hours=((hour_end - timedelta(hours=1)) - row.publish_time).total_seconds() / 3600.0,
                eligible=row.publish_time <= cutoff,
                excluded_reason=None if row.publish_time <= cutoff else "after_cutoff",
                selected=winner_key == (row.publish_time, row.row_index),
            )
        )
    return evaluations
