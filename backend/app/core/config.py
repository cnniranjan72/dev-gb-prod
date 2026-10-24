from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "WindLens API"
    version: str = "1.0.0"
    data_mode: str = field(
        default_factory=lambda: os.environ.get("WINDLENS_DATA_MODE", "snapshot")
    )
    snapshot_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("WINDLENS_SNAPSHOT_DIR", "data/snapshots/latest")
        )
    )
    elexon_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1"
        )
    )
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origin.strip()
            for origin in os.environ.get(
                "WINDLENS_CORS_ORIGINS",
                "http://localhost:5173,http://localhost:4173",
            ).split(",")
            if origin.strip()
        )
    )
    request_timeout_s: float = field(
        default_factory=lambda: float(os.environ.get("WINDLENS_HTTP_TIMEOUT_S", "30"))
    )
    upstream_retries: int = field(
        default_factory=lambda: int(os.environ.get("WINDLENS_HTTP_RETRIES", "3"))
    )
    log_level: str = field(
        default_factory=lambda: os.environ.get("WINDLENS_LOG_LEVEL", "INFO")
    )
    api_host: str = field(
        default_factory=lambda: os.environ.get("WINDLENS_API_HOST", "0.0.0.0")
    )
    api_port: int = field(
        default_factory=lambda: int(os.environ.get("WINDLENS_API_PORT", "8000"))
    )


settings = Settings()
