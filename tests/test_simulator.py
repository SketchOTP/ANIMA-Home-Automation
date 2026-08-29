from __future__ import annotations

import pytest

from anima_ha.simulator import run


def test_simulator_once_is_framework_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANIMA_DATABASE_URL", "postgresql://example")
    monkeypatch.setenv("ANIMA_LOG_LEVEL", "CRITICAL")
    assert run(once=True) == 0
