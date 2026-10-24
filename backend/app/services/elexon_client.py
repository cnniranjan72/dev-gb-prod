from __future__ import annotations

import time

import httpx

from ..core.config import Settings
from ..services.loader import normalize_actuals, normalize_forecasts


class ElexonClient:
    """Thin, retried access to the BMRS v1 datasets API (live mode)."""

    def __init__(self, settings: Settings):
        self.base_url = settings.elexon_base_url.rstrip("/")
        self.timeout = settings.request_timeout_s
        self.retries = settings.upstream_retries
        self.client = httpx.Client(timeout=self.timeout)

    def _request(self, path: str, params: dict) -> dict | list:
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.5 * 2 ** (attempt - 1))
        raise ElexonUnavailable(f"Elexon request failed after {self.retries} attempts: {url}") from last_error

    def fetch_fuelhh_wind(self, settlement_date_from: str, settlement_date_to: str) -> list[dict]:
        payload = self._request(
            "/datasets/FUELHH/stream",
            {
                "settlementDateFrom": settlement_date_from,
                "settlementDateTo": settlement_date_to,
                "fuelType": "WIND",
                "format": "json",
            },
        )
        records = payload["data"] if isinstance(payload, dict) else payload
        return list(records)

    def wind_actuals(self, settlement_date_from: str, settlement_date_to: str) -> list:
        processed = normalize_actuals(self.fetch_fuelhh_wind(settlement_date_from, settlement_date_to))
        return settle_duplicates(processed)

    def fetch_windfor(self, publish_from: str, publish_to: str) -> list[dict]:
        payload = self._request(
            "/datasets/WINDFOR/stream",
            {"publishDateTimeFrom": publish_from, "publishDateTimeTo": publish_to},
        )
        records = payload["data"] if isinstance(payload, dict) else payload
        return list(records)

    def wind_forecasts(self, publish_from: str, publish_to: str) -> list:
        processed = normalize_forecasts(self.fetch_windfor(publish_from, publish_to))
        return settle_duplicates(processed)

    def close(self) -> None:
        self.client.close()


def settle_duplicates(rows):
    """Publish-time dedupe with the same policy the offline loader uses."""
    from ..services.loader import dedupe_actuals, dedupe_forecasts

    if not rows:
        return []
    first = rows[0]
    if hasattr(first, "interval_start"):
        return dedupe_actuals(list(rows))
    return dedupe_forecasts(list(rows)) if hasattr(first, "hour_end") else list(rows)


class ElexonUnavailable(RuntimeError):
    """Raised when the upstream BMRS API cannot be reached after retries."""
