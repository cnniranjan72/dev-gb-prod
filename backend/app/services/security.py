"""Password hashing, JWT issuing/verification and RBAC guards.

Password hashing: PBKDF2-HMAC-SHA256 with a per-user random salt and a
calibrated iteration count (210k) — pure stdlib, deterministic bundle size,
no native build deps (important for serverless).

JWTs: HS256 signed with `WINDLENS_JWT_SECRET`. Tokens embed subject (email),
role and exp/iat. 401 = bad/missing token; 403 = token valid but insufficient
role (distinguishable by clients for UX).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..core.config import settings

logger = logging.getLogger("windlens.security")

PBKDF2_ITERATIONS = 210_000
_SALT_BYTES = 16
_HASH_BYTES = 32
_TOKEN_TTL_SECONDS = 24 * 3600


def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=_HASH_BYTES)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
        base64.urlsafe_b64encode(digest).decode("ascii").rstrip("="),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm_version, iterations_b64, salt_b64, hash_b64 = stored.split("$", 3)
        if algorithm_version != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode((salt_b64 + "==").encode("ascii"))
        expected = base64.urlsafe_b64decode((hash_b64 + "==").encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations_b64), dklen=len(expected)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _jwt_secret() -> str:
    from_env = os.environ.get("WINDLENS_JWT_SECRET", "").strip()
    if from_env:
        return from_env
    logger.warning("WINDLENS_JWT_SECRET not set; using the published development fallback — rotate in production")
    return getattr(settings, "jwt_secret_dev_fallback", "windlens-dev-secret-rotate-me")


def create_access_token(*, subject: str, role: str, ttl_seconds: int = _TOKEN_TTL_SECONDS) -> str:
    now = int(time.time())
    payload = {"sub": subject, "role": role, "iat": now, "exp": now + ttl_seconds}
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc
    if not payload.get("sub") or not payload.get("role"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="malformed token")
    return payload


bearer_scheme = HTTPBearer(auto_error=False, description="JWT from /api/auth/login")


class JwtAuth:
    """FastAPI dependency with a `payload` attribute after resolution."""

    def __init__(self, payload: dict):
        self.payload = payload
        self.sub: str = payload["sub"]
        self.role: str = payload["role"]


def get_current_session(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> JwtAuth:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return JwtAuth(decode_access_token(credentials.credentials))


def require_role(minimum_role: str):
    """Coarse-but-explicit RBAC gate. Role rank order: viewer < analyst < admin."""
    _order = {"viewer": 0, "analyst": 1, "admin": 2}

    def guard(session: Annotated[JwtAuth, Depends(get_current_session)]) -> JwtAuth:
        if _order.get(session.role, -1) < _order.get(minimum_role, 99):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role '{minimum_role}' required (you have '{session.role}')",
            )
        return session

    return guard
