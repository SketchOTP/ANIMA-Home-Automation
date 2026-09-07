from __future__ import annotations

import re
from pathlib import Path

import pytest

from anima_ha.config import ConfigurationError, RuntimeConfig


def test_configuration_is_environment_driven() -> None:
    config = RuntimeConfig.from_environment(
        {
            "ANIMA_ENV": "test",
            "ANIMA_LOG_LEVEL": "debug",
            "ANIMA_DATABASE_URL": "postgresql://example",
            "ANIMA_DB_CONNECT_TIMEOUT": "9",
        }
    )
    assert config.environment == "test"
    assert config.log_level == "DEBUG"
    assert config.database_url == "postgresql://example"
    assert config.database_connect_timeout == 9


def test_configuration_requires_database_url() -> None:
    with pytest.raises(ConfigurationError, match="ANIMA_DATABASE_URL"):
        RuntimeConfig.from_environment({})


def test_searxng_compose_probe_checks_local_liveness_not_external_search() -> None:
    # Static config guard only: a healthy HTTP process does not prove search
    # quality or external-engine availability. Do not read .env or run Compose.
    compose = (Path(__file__).resolve().parents[1] / "compose.yaml").read_text(encoding="utf-8")
    service = compose.split("\n  searxng:\n", 1)[1].split("\n  ui:\n", 1)[0]
    probe = service.split("    healthcheck:\n", 1)[1].split("    restart:", 1)[0]
    assert re.findall(r'https?://[^"\s]+', probe) == ["http://127.0.0.1:8080/healthz"]
    assert "/search" not in probe
    assert "timeout=3" in probe
    assert "      interval: 5s\n" in probe
    assert "      timeout: 5s\n" in probe
    assert "      retries: 12\n" in probe
