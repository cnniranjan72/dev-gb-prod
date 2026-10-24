from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.state import set_dataset
from app.services.dataset import ForecastDataset
from tests.fixtures import write_synthetic_snapshot


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("WINDLENS_AUTH_STORE_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("WINDLENS_JWT_SECRET", "test-secret")
    from app.services import users as users_service

    users_service._store = None
    snapshot_dir = write_synthetic_snapshot(tmp_path)
    dataset = ForecastDataset.from_snapshot(snapshot_dir)
    set_dataset(dataset)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        login = test_client.post(
            "/api/auth/login",
            json={"email": "admin@windlens.demo", "password": "windlens-admin"},
        )
        assert login.status_code == 200, login.text
        test_client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
        yield test_client
    from app.api.state import DatasetState

    DatasetState.instance = None
    users_service._store = None


BASE = {"date": "2026-01-15"}


def test_health_reflacts_loaded_dataset(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["actual_rows"] == 47
    assert body["dataset_start_utc"].startswith("2026-01-15T00:00:00Z")


def test_series_returns_half_hour_rows_with_selected_forecasts(client):
    response = client.get("/api/series", params={**BASE})
    assert response.status_code == 200
    body = response.json()
    assert len(body["points"]) == 48
    assert body["cutoff"]["mode"] == "preset" and body["cutoff"]["preset"] == "day_ahead_1030"
    first = body["points"][0]
    assert first["actual_mw"] == 401
    assert first["forecast_mw"] == 900
    assert first["forecast_publish_time_utc"] == "2026-01-14T09:30:00Z"
    unavailable = body["points"][2]
    assert unavailable["available"] is False and unavailable["forecast_mw"] is None


def test_series_rejects_invalid_date(client):
    response = client.get("/api/series", params={"date": "15/01/2026"})
    assert response.status_code == 400
    response = client.get("/api/series", params={"date": "2026-02-01"})
    assert response.status_code == 404  # outside dataset coverage


def test_series_rejects_unknown_preset(client):
    response = client.get("/api/series", params={"date": "2026-01-15", "preset": "banana"})
    assert response.status_code == 400


def test_custom_cutoff_is_validated_and_applied(client):
    response = client.get("/api/series", params={"date": "2026-01-15", "preset": "custom"})
    assert response.status_code == 400  # custom without cutoff value
    response = client.get(
        "/api/series", params={"date": "2026-01-15", "preset": "custom", "cutoff": "2026-01-14T15:00Z"}
    )
    assert response.status_code == 200
    points = response.json()["points"]
    assert points[0]["forecast_mw"] == 1000 and points[2]["forecast_mw"] is None


def test_summary_metrics_match_series(client):
    summary = client.get("/api/summary", params={**BASE}).json()
    series = client.get("/api/series", params={**BASE}).json()
    assert summary["metrics"]["count"] == 6
    errors = [p["error_mw"] for p in series["points"] if p["error_mw"] is not None]
    mean_bias = sum(errors) / len(errors)
    assert abs(summary["metrics"]["mean_bias_mw"] - mean_bias) < 0.2
    assert summary["coverage"]["valid_pairs"] == 6


def test_vintages_endpoint_lists_eligibility_and_selected(client):
    response = client.get("/api/vintages", params={**BASE, "period": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["selected_forecast_mw"] == 900
    assert body["hour_end_label_utc"] == "2026-01-15T01:00:00Z"
    eligible = [v for v in body["vintages"] if v["eligible"]]
    excluded = [v for v in body["vintages"] if not v["eligible"]]
    assert len(eligible) == 1 and eligible[0]["selected"]
    assert len(excluded) >= 2 and all(v["excluded_reason"] == "after_cutoff" for v in excluded)


def test_vintages_period_without_any_forecast(client):
    response = client.get("/api/vintages", params={**BASE, "period": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["selected_forecast_mw"] is None


def test_vintages_rejects_period_bounds(client):
    response = client.get("/api/vintages", params={**BASE, "period": 0})
    assert response.status_code == 422
    response = client.get("/api/vintages", params={**BASE, "period": 51})
    assert response.status_code == 422


def test_accuracy_endpoint_day_counts(client):
    response = client.get("/api/accuracy", params={})
    assert response.status_code == 200
    body = response.json()
    assert body["overall"]["count"] == 6
    assert len(body["by_day"]) == 1
    hours = {row["london_hour"]: row for row in body["by_london_hour"]}
    assert hours[0]["count"] == 2  # hour 0 (London) = top of day GMT January


def test_metadata_round_trips_manifest(client):
    body = client.get("/api/metadata").json()
    assert body["source"] == "synthetic test fixture"
    assert body["alignment_convention"] == "hour-ending"
