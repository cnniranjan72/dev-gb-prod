"""User accounts with roles, PBKDF2-verified passwords and a JSON persistence hook.

Persistence: `data/auth/users.json` when the filesystem allows writes (local dev,
containers); falls back to in-memory + env-seeded accounts on read-only filesystems
(serverless) or when the file is missing. Seeded demo accounts make the challenge
demo reproducible: the admin can be overridden by env vars.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from .security import hash_password

logger = logging.getLogger("windlens.users")

ROLES = ("viewer", "analyst", "admin")

DEFAULT_ADMIN_EMAIL = os.environ.get("WINDLENS_AUTH_ADMIN_EMAIL", "admin@windlens.demo")
DEFAULT_ADMIN_PASSWORD = os.environ.get("WINDLENS_AUTH_ADMIN_PASSWORD", "windlens-admin")

DEMO_SEEDS = (
    {"email": DEFAULT_ADMIN_EMAIL, "password": DEFAULT_ADMIN_PASSWORD, "role": "admin"},
    {"email": "analyst@windlens.demo", "password": "windlens-analyst", "role": "analyst"},
    {"email": "viewer@windlens.demo", "password": "windlens-viewer", "role": "viewer"},
)


@dataclass(frozen=True)
class UserRecord:
    email: str
    password_hash: str
    role: str


class UserStore:
    def __init__(self, base_dir: Path):
        self._file = base_dir / "users.json"
        self._users: dict[str, UserRecord] = {}
        self._load_or_seed()

    # --- persistence ------------------------------------------------------
    def _load_or_seed(self) -> None:
        if self._file.exists():
            try:
                raw = json.loads(self._file.read_text(encoding="utf-8"))
                for row in raw:
                    self._register(
                        UserRecord(
                            email=row["email"].strip().lower(),
                            password_hash=row["password_hash"],
                            role=row.get("role", "viewer"),
                        )
                    )
                # Env admin always beats stale seeded records.
                self._seed_env_admin()
                logger.info("user store loaded from %s (%d users)", self._file, len(self._users))
                return
            except (OSError, ValueError, KeyError, TypeError) as exc:
                logger.warning("user store file unreadable (%s); reseeding", exc)
        for seed in DEMO_SEEDS:
            self._register(
                UserRecord(
                    email=seed["email"].strip().lower(),
                    password_hash=hash_password(seed["password"]),
                    role=seed["role"],
                )
            )
        self._try_persist()

    def _seed_env_admin(self) -> None:
        admin = UserRecord(
            email=DEFAULT_ADMIN_EMAIL.strip().lower(),
            password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
            role="admin",
        )
        existing = self._users.get(admin.email)
        # Re-hash only when the stored record is not verifiable against env password
        # semantics changed (cheap check would require the plaintext; re-seed instead
        # when the role has drifted).
        if existing is None or existing.role != "admin":
            self._users[admin.email] = admin
            self._try_persist()

    def _try_persist(self) -> None:
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            self._file.write_text(
                json.dumps(
                    [
                        {"email": u.email, "password_hash": u.password_hash, "role": u.role}
                        for u in self._users.values()
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.info(
                "user store not persisted (%s); running with %d in-memory accounts", exc, len(self._users)
            )

    # --- operations -------------------------------------------------------
    def _register(self, record: UserRecord) -> None:
        self._users[record.email] = record

    def authenticate(self, email: str, password: str) -> tuple[UserRecord, bool]:
        """Return (user, success). Constant-ish behavior on missing users."""
        from .security import verify_password

        record = self._users.get(email.strip().lower())
        if record is None:
            # Burn comparable time to blunt username probing.
            verify_password("not-the-real-password-timing-equalizer", hash_password("x"))
            return UserRecord(email=email, password_hash="", role=""), False
        return record, verify_password(password, record.password_hash)

    def create_user(self, email: str, password: str, role: str = "viewer") -> UserRecord:
        email = email.strip().lower()
        if email in self._users:
            raise ValueError("email already registered")
        if role not in ROLES or "@" not in email or len(password) < 8:
            raise ValueError("invalid email, password (<8 chars) or role")
        record = UserRecord(email=email, password_hash=hash_password(password), role=role)
        self._register(record)
        self._try_persist()
        return record

    def set_role(self, email: str, role: str) -> UserRecord:
        email = email.strip().lower()
        if role not in ROLES:
            raise ValueError("unknown role")
        record = self._users.get(email)
        if record is None:
            raise KeyError("user not found")
        updated = UserRecord(email=record.email, password_hash=record.password_hash, role=role)
        self._users[email] = updated
        self._try_persist()
        return updated

    def delete_user(self, email: str, *, keep_at_least_one_admin: bool = True) -> bool:
        record = self._users.get(email.strip().lower())
        if record is None:
            raise KeyError("user not found")
        if keep_at_least_one_admin and self._admins() == 1 and record.role == "admin":
            raise ValueError("cannot revoke the last admin")
        del self._users[record.email]
        self._try_persist()
        return True

    def list_users(self) -> list[UserRecord]:
        return sorted(self._users.values(), key=lambda r: (r.email != DEFAULT_ADMIN_EMAIL.lower(), r.email))

    def _admins(self) -> int:
        return sum(1 for r in self._users.values() if r.role == "admin")


_store: UserStore | None = None


def get_user_store() -> UserStore:
    global _store
    if _store is None:
        base = Path(
            os.environ.get(
                "WINDLENS_AUTH_STORE_DIR",
                os.environ.get("WINDLENS_SNAPSHOT_DIR", "data/snapshots/latest"),
            )
        )
        _store = UserStore(base.parent / "auth")
    return _store
