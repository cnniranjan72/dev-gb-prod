from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

from ..core.config import Settings
from .dataset import ForecastDataset

DEFAULT_LIVE_START = date(2026, 1, 1)
DEFAULT_LIVE_END = date(2026, 2, 1)
# WINDFOR vintages need publication history reaching before period start so
# that the day-ahead cutoff for the first delivery day has eligible rows.
PUBLICATION_PAD_BEFORE = timedelta(hours=48)
PUBLICATION_PAD_AFTER = timedelta(hours=72)


def _live_window() -> tuple[date, date]:
    start = date.fromisoformat(os.environ.get("WINDLENS_LIVE_SETTLEMENT_START", DEFAULT_LIVE_START.isoformat()))
    end_exclusive = date.fromisoformat(os.environ.get("WINDLENS_LIVE_SETTLEMENT_END", DEFAULT_LIVE_END.isoformat()))
    if end_exclusive <= start:
        raise RuntimeError("WINDLENS_LIVE_SETTLEMENT_END must be after WINDLENS_LIVE_SETTLEMENT_START")
    return start, end_exclusive


def resolve_dataset(settings: Settings) -> ForecastDataset:
    """Live/snapshot resolution.

    snapshot mode (default, production): loads the canonicalised, validated
    snapshot under data/snapshots/latest (with manifest) — deterministic,
    fast, and reproducible.

    live mode: fetches the configured analysis window through the Elexon BMRS
    client at startup; used to demonstrate refresh capability.
    """
    if settings.data_mode == "snapshot":
        return ForecastDataset.from_snapshot(settings.snapshot_dir)
    if settings.data_mode == "live":
        from .elexon_client import ElexonClient

        start, end_exclusive = _live_window()
        client = ElexonClient(settings)
        actual_records = client.fetch_fuelhh_wind(start.isoformat(), (end_exclusive - timedelta(days=1)).isoformat())
        publication_from = (
            datetime(start.year, start.month, start.day, tzinfo=timezone.utc) - PUBLICATION_PAD_BEFORE
        ).isoformat()
        publication_to = (
            datetime(end_exclusive.year, end_exclusive.month, end_exclusive.day, tzinfo=timezone.utc)
            + PUBLICATION_PAD_AFTER
        ).isoformat()
        forecast_records = client.fetch_windfor(publication_from, publication_to)
        return ForecastDataset.from_records(
            actual_records,
            forecast_records,
            {
                "mode": "live",
                "period": {"settlement_from": start.isoformat(), "settlement_to": (end_exclusive - timedelta(days=1)).isoformat()},
            },
        )
    raise RuntimeError(f"unsupported WINDLENS_DATA_MODE {settings.data_mode!r} (expected snapshot|live)")
