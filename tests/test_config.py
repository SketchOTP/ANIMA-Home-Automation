from __future__ import annotations

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
