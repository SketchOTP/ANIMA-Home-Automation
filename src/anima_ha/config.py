"""Environment-backed configuration for the local runtime baseline."""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationError(ValueError):
    """Raised when required runtime configuration is absent or invalid."""


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Configuration that is safe to vary by environment without household data."""

    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = ""
    database_connect_timeout: int = 5

    @classmethod
    def from_environment(cls, environ: dict[str, str] | None = None) -> RuntimeConfig:
        values = os.environ if environ is None else environ
        database_url = values.get("ANIMA_DATABASE_URL", "").strip()
        if not database_url:
            raise ConfigurationError("ANIMA_DATABASE_URL is required")

        try:
            timeout = int(values.get("ANIMA_DB_CONNECT_TIMEOUT", "5"))
        except ValueError as exc:
            raise ConfigurationError("ANIMA_DB_CONNECT_TIMEOUT must be an integer") from exc
        if timeout < 1 or timeout > 120:
            raise ConfigurationError("ANIMA_DB_CONNECT_TIMEOUT must be between 1 and 120")

        log_level = values.get("ANIMA_LOG_LEVEL", "INFO").upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError("ANIMA_LOG_LEVEL must be a standard logging level")

        return cls(
            environment=values.get("ANIMA_ENV", "development"),
            log_level=log_level,
            database_url=database_url,
            database_connect_timeout=timeout,
        )
