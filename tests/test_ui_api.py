from __future__ import annotations

from collections import deque
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from anima_ha.ui_api import (
    DEFAULT_HOUSEHOLD_ID,
    DEFAULT_PRINCIPAL_ID,
    UI_OAUTH_NONCE_COOKIE,
    JournalConversationIngress,
    UIConfig,
    UIEventBroadcaster,
    UIService,
    create_app,
    validate_ui_preferences,
)


def authenticated_client() -> tuple[TestClient, str, UIService]:
    service = UIService(config=UIConfig(test_auth_enabled=True))
    client = TestClient(create_app(service), follow_redirects=False)
    login = client.get("/auth/login")
    assert login.status_code == 307
    callback = client.get(login.headers["location"])
    assert callback.status_code == 307
    csrf = callback.headers["x-anima-csrf"]
    return client, csrf, service


class DeviceCommandStub:
    def device_inventory(self, identity: object) -> dict[str, object]:
        del identity
        return {
            "status": "AVAILABLE",
            "items": [
                {
                    "external_object_kind": "device",
                    "external_id": "ha-device",
                    "present": True,
                    "metadata": {"name": "SenseGuard Basement"},
                }
            ],
        }

    def device_mutation(
        self, identity: object, operation: str, payload: dict[str, object]
    ) -> dict[str, object]:
        del identity
        return {"status": "SUCCEEDED", "operation": operation, "result": payload}

    def alert_policy_mutation(
        self, identity: object, operation: str, payload: dict[str, object]
    ) -> dict[str, object]:
        del identity
        return {"status": "SUCCEEDED", "operation": operation, "result": {"policy": payload}}

    def notification_route_mutation(
        self, identity: object, operation: str, payload: dict[str, object]
    ) -> dict[str, object]:
        del identity
        return {"status": "SUCCEEDED", "operation": operation, "result": {"route": payload}}


def test_health_is_public_but_household_data_requires_session() -> None:
    app = create_app(UIService(config=UIConfig(test_auth_enabled=True)))
    client = TestClient(app)
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/api/v1/home").status_code == 401


def test_device_routes_return_registry_and_route_bounded_mutations() -> None:
    service = UIService(config=UIConfig(test_auth_enabled=True), commands=DeviceCommandStub())  # type: ignore[arg-type]
    client = TestClient(create_app(service), follow_redirects=False)
    login = client.get("/auth/login")
    callback = client.get(login.headers["location"])
    csrf = callback.headers["x-anima-csrf"]
    assert client.get("/api/v1/devices").json()["items"][0]["external_id"] == "ha-device"
    response = client.post(
        "/api/v1/devices/permit-pairing",
        json={"payload": {"duration_seconds": 60}},
        headers={"X-Anima-CSRF": csrf, "Origin": "http://testserver"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "SUCCEEDED"
    assert response.json()["operation"] == "permit-pairing"


def test_alert_policy_route_is_bounded_and_household_scoped() -> None:
    service = UIService(config=UIConfig(test_auth_enabled=True), commands=DeviceCommandStub())  # type: ignore[arg-type]
    client = TestClient(create_app(service), follow_redirects=False)
    login = client.get("/auth/login")
    callback = client.get(login.headers["location"])
    csrf = callback.headers["x-anima-csrf"]
    assert client.get("/api/v1/alerts/policies").json()["items"] == []
    response = client.post(
        "/api/v1/alerts/policies",
        json={"payload": {"event_type": "senseguard.event", "resource_ids": ["resource"]}},
        headers={"X-Anima-CSRF": csrf, "Origin": "http://testserver"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "SUCCEEDED"


def test_notification_route_is_bounded_and_keeps_destination_server_owned() -> None:
    service = UIService(config=UIConfig(test_auth_enabled=True), commands=DeviceCommandStub())  # type: ignore[arg-type]
    client = TestClient(create_app(service), follow_redirects=False)
    login = client.get("/auth/login")
    callback = client.get(login.headers["location"])
    csrf = callback.headers["x-anima-csrf"]
    assert client.get("/api/v1/notifications/routes").json()["items"] == []
    response = client.post(
        "/api/v1/notifications/routes",
        json={"payload": {"label": "Overnight alerts", "minimum_priority": 80}},
        headers={"X-Anima-CSRF": csrf, "Origin": "http://testserver"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "SUCCEEDED"
    assert "destination" not in response.json()["result"]["route"]


def test_oauth_state_is_single_use_and_session_stores_only_hashes() -> None:
    client, csrf, service = authenticated_client()
    bootstrap = client.get("/api/v1/bootstrap")
    assert bootstrap.status_code == 200
    refreshed_csrf = bootstrap.json()["csrf_token"]
    record = next(iter(service.sessions.records.values()))  # type: ignore[attr-defined]
    assert record.secret_hash != client.cookies.get("anima_session").split(".", 1)[1]  # type: ignore[union-attr]
    assert csrf != refreshed_csrf
    assert client.get("/auth/callback?code=anima-test-code&state=used").status_code == 400


def test_oauth_state_requires_the_browser_bound_nonce_and_is_single_use() -> None:
    service = UIService(config=UIConfig(test_auth_enabled=True))
    state = service.create_oauth_state()
    nonce = service.oauth_nonce(state)
    assert nonce is not None
    assert service.consume_oauth_state(state, "wrong") is False
    assert service.consume_oauth_state(state, nonce) is False

    expired = service.create_oauth_state()
    expired_nonce = service.oauth_nonce(expired)
    assert expired_nonce is not None
    service._oauth_states[expired] = (
        expired_nonce,
        datetime.now(UTC) - timedelta(seconds=1),
    )
    assert service.consume_oauth_state(expired, expired_nonce) is False


def test_ui_preferences_are_bounded_and_persist_through_the_api() -> None:
    client, csrf, _ = authenticated_client()
    assert client.get("/api/v1/settings").json()["settings"]["appearance"] == "night"
    response = client.put(
        "/api/v1/settings",
        json={"payload": {"appearance": "light", "accent": "sage", "reduced_motion": True}},
        headers={"X-Anima-CSRF": csrf, "Origin": "http://testserver"},
    )
    assert response.status_code == 200
    assert response.json()["settings"]["accent"] == "sage"
    assert client.get("/api/v1/settings").json()["settings"]["reduced_motion"] is True

    rejected = client.put(
        "/api/v1/settings",
        json={"payload": {"appearance": "execute-shell"}},
        headers={"X-Anima-CSRF": csrf, "Origin": "http://testserver"},
    )
    assert rejected.status_code == 400
    assert UI_OAUTH_NONCE_COOKIE not in client.cookies


def test_home_is_anima_view_model_and_mutations_require_csrf_and_origin() -> None:
    client, _, _ = authenticated_client()
    bootstrap = client.get("/api/v1/bootstrap").json()
    home = client.get("/api/v1/home")
    assert home.status_code == 200
    assert "household" in home.json()
    assert "anima_event_journal" not in home.text
    assert client.post("/api/v1/conversation", json={"text": "hello"}).status_code == 403
    response = client.post(
        "/api/v1/conversation",
        json={"text": "What is happening at home?"},
        headers={
            "X-Anima-CSRF": bootstrap["csrf_token"],
            "Origin": "http://testserver",
        },
    )
    assert response.status_code == 200
    assert response.json()["trace"]["origin"] == "DIRECT_USER"


def test_home_exposes_product_surfaces_and_legacy_preferences_migrate() -> None:
    client, _, _ = authenticated_client()
    home = client.get("/api/v1/home").json()
    assert home["rooms"][0]["name"] == "Living room"
    assert home["rooms"][0]["devices"][0]["name"] == "Demo lamp"
    assert home["notifications"][0]["summary"] == "Anima interface ready"
    assert home["health"]["status"] == "DEGRADED"
    migrated = validate_ui_preferences(
        {"version": 1, "visible_widgets": ["status"], "widget_order": ["status"]}
    )
    assert migrated["version"] == 2
    assert migrated["visible_widgets"] == ["status", "household", "reports", "health"]


def test_production_conversation_requires_the_real_runtime_bridge() -> None:
    client, _, service = authenticated_client()
    assert isinstance(service.conversation, JournalConversationIngress)
    service.conversation.fallback_enabled = False
    bootstrap = client.get("/api/v1/bootstrap").json()
    response = client.post(
        "/api/v1/conversation",
        json={"text": "hello"},
        headers={
            "X-Anima-CSRF": bootstrap["csrf_token"],
            "Origin": "http://testserver",
        },
    )
    assert response.status_code == 503
    assert service.conversation.events_seen[-1].event_type == "user.request"


def test_unmapped_home_assistant_user_fails_closed() -> None:
    service = UIService(config=UIConfig(test_auth_enabled=True), ha_user_map={})
    try:
        service.map_ha_user("not-commissioned")
    except Exception as exc:
        assert str(exc) == "PRINCIPAL_MAPPING_REQUIRED"
    else:
        raise AssertionError("unmapped HA user was accepted")


def test_identity_evidence_is_authenticated_not_strong_by_default() -> None:
    service = UIService(config=UIConfig(test_auth_enabled=True))
    identity = service.map_ha_user("test-ha-user")
    assert identity.household_id == DEFAULT_HOUSEHOLD_ID
    assert identity.principal_id == DEFAULT_PRINCIPAL_ID
    assert identity.evidence.assurance.value == "AUTHENTICATED"
    assert identity.evidence.metadata == {}


def test_sse_invalidation_fanout_is_bounded_and_unsubscribable() -> None:
    broadcaster = UIEventBroadcaster()
    queue = broadcaster.subscribe()
    assert isinstance(queue, deque)
    broadcaster.publish("home.invalidated")
    assert list(queue) == ["home.invalidated"]
    broadcaster.unsubscribe(queue)
    broadcaster.publish("tasks.changed")
    assert list(queue) == ["home.invalidated"]
