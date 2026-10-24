"""JWT authentication and RBAC account management endpoints.

Endpoints:
    POST /api/auth/login          -> issue JWT (any seeded/registered account)
    GET  /api/auth/me             -> current identity (viewer+)
    GET  /api/auth/users          -> list accounts (admin)
    POST /api/auth/users          -> create account (admin)
    POST /api/auth/users/{email}/role -> change role (admin)
    DELETE /api/auth/users/{email}    -> delete account (admin; self-delete allowed
                                         for non-admins; last admin protected)

Analytics endpoints elsewhere in the app gate on roles via
`require_role("viewer" | "analyst")`; /api/health and docs stay public.
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from ..schemas import dtos
from ..services.security import JwtAuth, create_access_token, get_current_session, require_role
from ..services.users import get_user_store

logger = logging.getLogger("windlens.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=1024)
    role: str = Field(default="viewer", pattern=r"^(viewer|analyst|admin)$")


class RoleChangeRequest(BaseModel):
    role: str = Field(pattern=r"^(viewer|analyst|admin)$")


Session = Annotated[JwtAuth, Depends(get_current_session)]
Admin = Annotated[JwtAuth, Depends(require_role("admin"))]


def _token_for(record) -> dtos.LoginResponse:
    return dtos.LoginResponse(
        access_token=create_access_token(subject=record.email, role=record.role),
        token_type="bearer",
        expires_in=24 * 3600,
        email=record.email,
        role=record.role,
    )


@router.post("/login", response_model=dtos.LoginResponse)
def login(body: LoginRequest) -> dtos.LoginResponse:
    store = get_user_store()
    record, ok = store.authenticate(body.email, body.password)
    if not ok:
        logger.info("failed login for %s", body.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    return _token_for(record)


@router.get("/me", response_model=dtos.UserOut)
def me(session: Session) -> dtos.UserOut:
    return dtos.UserOut(email=session.sub, role=session.role)


@router.get("/users", response_model=list[dtos.UserOut])
def list_users(_: Admin) -> list[dtos.UserOut]:
    return [
        dtos.UserOut(email=u.email, role=u.role)
        for u in get_user_store().list_users()
    ]


@router.post("/users", response_model=dtos.UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: RegisterRequest, _: Admin) -> dtos.UserOut:
    try:
        record = get_user_store().create_user(body.email, body.password, body.role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return dtos.UserOut(email=record.email, role=record.role)


@router.post("/users/{email}/role", response_model=dtos.UserOut)
def change_role(email: str, body: RoleChangeRequest, _admin: Admin) -> dtos.UserOut:
    try:
        record = get_user_store().set_role(email, body.role)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return dtos.UserOut(email=record.email, role=record.role)


@router.delete("/users/{email}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(email: str, session: Session) -> Response:
    store = get_user_store()
    target = email.strip().lower()
    is_admin = session.role == "admin"
    if not is_admin and target != session.sub:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin required")
    try:
        store.delete_user(target)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
