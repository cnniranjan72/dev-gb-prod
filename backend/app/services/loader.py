from __future__ import annotations

from dataclasses import dataclass

from ..services.conventions import settlement_date_local, to_utc

VALID_FUELTYPES = {"WIND"}


@dataclass(frozen=True)
class ActualRow:
    interval_start: object  # tz-aware UTC datetime, half [start, start+30m)
    settlement_date: object  # datetime.date (Europe/London settlement view)
    generation_mw: object  # float | None
    publish_time: object  # tz-aware UTC datetime of the release that delivered this record
    source_key: str = "FUELHH"


@dataclass(frozen=True)
class ForecastRow:
    hour_end: object  # tz-aware UTC datetime; raw WINDFOR startTime label
    publish_time: object  # tz-aware UTC datetime
    generation_mw: object  # float | None
    row_index: int  # source order, for deterministic tie-breaks
    source_key: str = "WINDFOR"


def _parse_generation(value: object) -> object:
    """Numeric policy: keep explicit null as None; integers/strings parse to float.

    Never coerces a missing surface value into 0.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_actuals(records: list[dict]) -> list[ActualRow]:
    rows: list[ActualRow] = []
    for record in records:
        fuel_type = record.get("fuelType")
        if fuel_type != "WIND":
            continue
        start = record.get("startTime")
        publish = record.get("publishTime")
        if not start or not publish:
            continue
        rows.append(
            ActualRow(
                interval_start=to_utc(start),
                settlement_date=settlement_date_local(to_utc(start)),
                generation_mw=_parse_generation(record.get("generation")),
                publish_time=to_utc(publish),
            )
        )
    return rows


def dedupe_actuals(rows: list[ActualRow]) -> list[ActualRow]:
    """Deterministic re-release resolution: latest publishTime per interval wins;
    ties break to the later source order.
    """
    best: dict[object, tuple[int, ActualRow]] = {}
    for index, row in enumerate(rows):
        current = best.get(row.interval_start)
        if current is None or row.publish_time >= current[1].publish_time:
            best[row.interval_start] = (index, row)
    return [entry[1] for key, entry in sorted(best.items(), key=lambda item: item[0])]


def normalize_forecasts(records: list[dict]) -> list[ForecastRow]:
    rows: list[ForecastRow] = []
    for index, record in enumerate(records):
        start = record.get("startTime")
        publish = record.get("publishTime")
        if not start or not publish:
            continue
        rows.append(
            ForecastRow(
                hour_end=to_utc(start),
                publish_time=to_utc(publish),
                generation_mw=_parse_generation(record.get("generation")),
                row_index=index,
            )
        )
    return rows


def dedupe_forecasts(rows: list[ForecastRow]) -> list[ForecastRow]:
    """Deterministic duplicate both-key policy for (publishTime, hour_end):
    keep the last occurrence in source order. Catalog confirmed no duplicates for
    January 2026; the rule is retained because corrected re-publishes are
    possible on any future refresh.
    """
    best: dict[tuple[object, object], ForecastRow] = {}
    for row in rows:
        key = (row.publish_time, row.hour_end)
        current = best.get(key)
        if current is None or row.row_index > current.row_index:
            best[key] = row
    return sorted(best.values(), key=lambda r: (r.publish_time, r.hour_end, r.row_index))
