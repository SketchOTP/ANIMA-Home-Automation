"""Normal app owns optional vendor readiness; owner cookies never grant relay access."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from anima_ha.ui_api import UIConfig, UIService, create_app


def test_vendor_status_uses_owner_session_and_does_not_claim_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANIMA_VENDOR_RELAY_CONFIG", raising=False)
    client = TestClient(create_app(UIService(config=UIConfig(test_auth_enabled=True))))
    assert client.get("/api/v1/vendor-events/status").status_code == 401
    client.get("/auth/login")
    response = client.get("/api/v1/vendor-events/status")
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "WAITING_APP_SETUP"
    assert data["enabled"] is False
    assert {item["vendor"] for item in data["vendors"]} == {"tapo", "wansview"}
    assert all(item["last_receipt_at"] is None for item in data["vendors"])
    assert client.post("/api/v1/vendor-events/receive", json={}).status_code == 401


def test_invalid_vendor_configuration_does_not_leak_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    secret_path = tmp_path / "PRIVATE-CONFIG-PATH"
    monkeypatch.setenv("ANIMA_VENDOR_RELAY_CONFIG", str(secret_path))
    client = TestClient(create_app(UIService(config=UIConfig(test_auth_enabled=True))))
    client.get("/auth/login")
    response = client.get("/api/v1/vendor-events/status")
    assert response.status_code == 503
    assert "PRIVATE-CONFIG-PATH" not in response.text
    assert client.get("/healthz").status_code == 200
