"""UI contract against actual ingress default; no provider/config/database access."""

from uuid import uuid4

from anima_ha.vendor_event_ingress import VendorEventIngress, VendorRelayConfig


def test_vendor_panel_contract_matches_real_disabled_backend_default() -> None:
    # Explicit constructor, never from_environment: no credentials or live setup.
    ingress = VendorEventIngress(config=VendorRelayConfig(), journal=None, graph=None)
    status = ingress.status(uuid4())
    assert status["configured"] is False and status["enabled"] is False
    assert status["state"] == "WAITING_APP_SETUP"
    assert {item["vendor"] for item in status["vendors"]} == {"tapo", "wansview"}
    for item in status["vendors"]:
        assert set(item) == {"vendor", "configured", "enabled", "state", "gates", "last_receipt_at"}
        assert item["configured"] is False and item["enabled"] is False
        assert item["state"] == "WAITING_APP_SETUP"
        assert item["last_receipt_at"] is None
        assert item["gates"] and all(isinstance(gate, str) for gate in item["gates"])
    tapo = next(item for item in status["vendors"] if item["vendor"] == "tapo")
    assert "HA_LOCK_MAPPING_REQUIRED" in tapo["gates"]
    wansview = next(item for item in status["vendors"] if item["vendor"] == "wansview")
    assert "PRODUCER_UNQUALIFIED" in wansview["gates"]
    assert "RELAY_DISABLED" in wansview["gates"]
