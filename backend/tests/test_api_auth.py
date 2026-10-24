"""Auth, RBAC and account-management regressions.

Covers: PBKDF2 roundtrip (guards against format-string drift), login
success/failure, JWT lifecycle (expiry, malformed tokens), the viewer < analyst
< admin roofline onanalytics endpoints, and admin account CRUD with the
last-admin protection.
"""
from __future__ import annotations

import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import users as users_service
from app.services.security import hash_password, verify_password
from tests.fixtures import write_synthetic_snapshot

ADMIN = {"email": "admin@windlens.demo", "password": "windlens-admin"}


@pytest.fixture()
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("WINDLENS_AUTH_STORE_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("WINDLENS_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    users_service._store = None
    set_dataset_for_tests(tmp_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    users_service._store = None


def set_dataset_for_tests(tmp_path):
    from app.api.state import set_dataset
    from app.services.dataset import ForecastDataset

    snapshot_dir = write_synthetic_snapshot(tmp_path)
    set_dataset(ForecastDataset.from_snapshot(snapshot_dir))


def login(client: TestClient, body: dict) -> str:
    response = client.post("/api/auth/login", json=body)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


# --- password hashing ------------------------------------------------------

def test_password_hash_roundtrip_and_rejection():
    stored = hash_password("london-bridge-42")
    assert stored.startswith("pbkdf2_sha256$210000$") and "$" not in stored.split("$")[2]
    assert verify_password("london-bridge-42", stored)
    assert not verify_password("london-bridge-43", stored)


def test_password_hash_is_salted_per_call():
    assert hash_password("x") != hash_password("x")


# --- login and tokens ------------------------------------------------------

def test_login_success_own_draft(api):
    response = api.post("/api/auth/login", json=ADMIN)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer" and body["role"] == "admin"
    assert jwt.decode(body["access_token"], options={"verify_signature": False})["sub"] == ADMIN["email"]


def test_api_auth_login_rejects_wrong_password(api):
    response = api.post(
        "/api/auth/login",
        json={"email": ADMIN["email"], "password": "totally-wrong"},
    )
    assert response.status_code == 401


def test_login_rate_unknown_user_behavior(api):
    response = api.post(
        "/api/auth/login",
        json={"email": "ghost@windlens.demo", "password": "whatever"},
    )
    assert response.status_code == 401


def test_gated_endpoint_requires_token(api):
    response = api.get("/api/summary", params={"date": "2026-01-15"})
    assert response.status_code == 401


def test_malformed_and_expired_tokens_rejected(api):
    api.headers.update({"Authorization": "Bearer not-a-jwt"})
    assert api.get("/api/auth/me").status_code == 401

    expired = jwt.encode(
        {"sub": ADMIN["email"], "role": "admin", "iat": int(time.time()) - 10, "exp": int(time.time()) - 5},
        "test-secret-at-least-32-bytes-long!!",
        algorithm="HS256",
    )
    api.headers.update({"Authorization": f"Bearer {expired}"})
    assert api.get("/api/auth/me").status_code == 401


def test_me_returns_session_identity(api):
    token = login(api, ADMIN)
    api.headers.update({"Authorization": f"Bearer {token}"})
    response = api.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


# --- RBAC matrix ------------------------------------------------------------

RBAC_CASES = [
    ("viewer@windlens.demo", "windlens-viewer"),
    ("analyst@windlens.demo", "windlens-analyst"),
]


@pytest.mark.parametrize("email,password,is_analyst", [(RBAC_CASES[0][0], RBAC_CASES[0][1], False), (RBAC_CASES[1][0], RBAC_CASES[1][1], True)])
def test_viewer_and_analyst_gates(api, email, password, is_analyst):
    token = login(api, {"email": email, "password": password})
    headers = {"Authorization": f"Bearer {token}"}
    vintage_status = 200 if is_analyst else 403

    assert api.get("/api/auth/me", headers=headers).status_code == 200
    assert api.get("/api/metadata", headers=headers).status_code == 200
    assert api.get("/api/series", params={"date": "2026-01-15"}, headers=headers).status_code == 200
    assert (
        api.get("/api/vintages", params={"date": "2026-01-15", "period": 1}, headers=headers).status_code
        == vintage_status
    )
    assert api.get("/api/auth/users", headers=headers).status_code == 403


def test_viewer_blocked_but_analyst_allowed_on_vintages(api):
    viewer = {"Authorization": f"Bearer {login(api, {"email": RBAC_CASES[0][0], "password": RBAC_CASES[0][1]})}"}
    analyst = {"Authorization": f"Bearer {login(api, {"email": RBAC_CASES[1][0], "password": RBAC_CASES[1][1]})}"}
    params = {"date": "2026-01-15", "period": 1}
    assert api.get("/api/vintages", params=params, headers=viewer).status_code == 403
    assert api.get("/api/vintages", params=params, headers=analyst).status_code == 200


# --- admin account management ----------------------------------------------

def test_admin_can_create_and_delete_user(api):
    headers = {"Authorization": f"Bearer {login(api, ADMIN)}"}

    created = api.post(
        "/api/auth/users",
        json={"email": "new.person@example.com", "password": "keep-it-secret", "role": "viewer"},
        headers=headers,
    )
    assert created.status_code == 201, created.text

    duplicate = api.post(
        "/api/auth/users",
        json={"email": "new.person@example.com", "password": "keep-it-secret"},
        headers=headers,
    )
    assert duplicate.status_code == 400

    tooshort = api.post(
        "/api/auth/users",
        json={"email": "weak@example.com", "password": "short", "role": "viewer"},
        headers=headers,
    )
    assert tooshort.status_code in (400, 422)

    listed = api.get("/api/auth/users", headers=headers)
    assert {u["email"] for u in listed.json()} >= {"new.person@example.com"}

    deleted = api.delete("/api/auth/users/new.person@example.com", headers=headers)
    assert deleted.status_code == 204
    assert {"new.person@example.com"} not in {u["email"] for u in api.get("/api/auth/users", headers=headers).json()}
    ghost_login = api.post(
        "/api/auth/login", json={"email": "new.person@example.com", "password": "keep-it-secret"}
    )
    assert ghost_login.status_code == 401


def test_last_admin_protected_from_self_deletion(api):
    headers = {"Authorization": f"Bearer {login(api, ADMIN)}"}
    assert api.delete("/api/auth/users/admin@windlens.demo", headers=headers).status_code == 409


def test_role_change_and_delete_guard(api):
    headers = {"Authorization": f"Bearer {login(api, ADMIN)}"}
    api.post(
        "/api/auth/users",
        json={"email": "temp.admin@example.com", "password": "temp-pass-123", "role": "admin"},
        headers=headers,
    )
    changed = api.post("/api/auth/users/temp.admin@example.com/role", json={"role": "viewer"}, headers=headers)
    assert changed.status_code == 200 and changed.json()["role"] == "viewer"

    unknown = api.post("/api/auth/users/nobody@example.com/role", json={"role": "viewer"}, headers=headers)
    assert unknown.status_code == 404

    bad_delete = api.delete("/api/auth/users/nobody@example.com", headers=headers)
    assert bad_delete.status_code == 404
