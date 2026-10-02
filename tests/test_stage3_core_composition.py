"""Isolated composition: no HA websocket, external query, model or owner fixture."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from test_stage2_delivery_postgres import isolated_url as isolated_url
from test_stage3_household_situation import observation
from test_stage3_household_situation import situation as situation

from anima_ha.alert_delivery import PostgresRequiredDelivery
from anima_ha.android_notifications import RelayRegistration
from anima_ha.attention import SentryEventPath
from anima_ha.events import DeliveryClass, EventEnvelope
from anima_ha.external import external_plugin
from anima_ha.ha_connection_setup import HAConnectionStore, HASetupError
from anima_ha.home_assistant import HomeAssistantPlugin
from anima_ha.household_learning import InitiativeConfig
from anima_ha.household_situation import diagnostic_coverage
from anima_ha.intelligence import IntelligenceRequestFactory
from anima_ha.ui_runtime import JournalEventWatcher, build_postgres_core
from anima_ha.vendor_event_ingress import VendorRelayConfig, VendorRelaySource


def compose(value: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> Any:
    import anima_ha.ui_runtime as module

    for name in (
        "ANIMA_HA_CONNECTION_FILE",
        "HA_ACCESS_TOKEN",
        "ANIMA_HA_ACCESS_TOKEN",
        "ANIMA_VENDOR_RELAY_CONFIG",
        "ANIMA_KNOWLEDGE_ROOT",
        "ANIMA_HOUSEHOLD_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ANIMA_SENTRY_HOUSEHOLD_ID", str(value["home"]))
    instance = str(uuid4())
    monkeypatch.setenv("ANIMA_HA_INSTANCE_ID", instance)
    monkeypatch.setenv("ANIMA_HA_PROVIDER_SCOPE", instance)
    monkeypatch.setenv("ANIMA_HA_WEBSOCKET_URL", "ws://127.0.0.1:9/api/websocket")
    monkeypatch.setenv("ANIMA_INTELLIGENCE_PROVIDER", "sentry")
    monkeypatch.setattr(JournalEventWatcher, "start", lambda _: None)
    monkeypatch.setattr(module, "_environment_secrets", lambda: {})
    return build_postgres_core(value["url"], watch_journal_events=True)


@pytest.mark.parametrize(
    "path",
    [
        SentryEventPath.IMMEDIATE_ANNOUNCEMENT_ONLY,
        SentryEventPath.ANNOUNCEMENT_AND_CONTEXTUAL_REASONING,
    ],
)
def test_core_without_ha_recovers_ring_and_required_speech_without_rich_context(
    situation: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    path: SentryEventPath,
) -> None:
    core = compose(situation, monkeypatch)
    assert core.home_assistant_adapter is None and core.action_refresher is None
    assert core.journal_event_watcher is not None
    assert not any(
        tool.plugin_id == "anima.provider.home-assistant" for tool in core.plugins.list_tools()
    )

    def forbidden_situation(_: UUID) -> dict[str, Any]:
        raise AssertionError("Rich context must not gate canonical speech")

    core.learning_service.situation_reader = forbidden_situation
    config = InitiativeConfig().to_payload()
    core.learning_service.configure(
        situation["home"],
        situation["owner"],
        {
            **config,
            "expected_version": None,
            "device_notifications": [
                {
                    "resource_id": str(situation["sensor"]),
                    "mode": "ALWAYS",
                    "start_local": "00:00",
                    "end_local": "23:59",
                    "timezone": "UTC",
                    "sentry_path": path.value,
                }
            ],
        },
    )
    event_id = observation(situation)
    assert core.journal_event_watcher.recover_pending() == 1
    assert core.journal_event_watcher.delivery_state == "CURRENT"
    with psycopg.connect(situation["url"]) as conn:
        rows = conn.execute(
            "SELECT request_id,request_metadata,provider_invocation_started "
            "FROM anima_intelligence_requests WHERE household_id=%s AND causation_id=%s",
            (situation["home"], event_id),
        ).fetchall()
    assert len(rows) == 1 and rows[0][2] is False
    assert rows[0][1]["required_delivery"]["state"] == "PENDING"
    assert rows[0][1]["sentry_event_path"] == path.value
    # Another callback/restart consumes the same identity, not a new request.
    row = core.journal.get(event_id)
    assert row is not None and core.event_dispatcher is not None
    position = core.journal.position(event_id)
    assert position is not None
    core.event_dispatcher(row, position)
    ledger = PostgresRequiredDelivery(situation["url"])

    def disposition(request: Any) -> dict[str, Any]:
        result: dict[str, Any] = core.initiative_context(request)["notification"]
        return result

    claimed = ledger.next(
        household_id=situation["home"],
        client_id="isolated",
        not_before=datetime.now(UTC) - timedelta(seconds=1),
        disposition=disposition,
    )
    assert claimed["request_id"] == str(rows[0][0])
    started = ledger.transition(
        UUID(claimed["request_id"]),
        household_id=situation["home"],
        client_id="isolated",
        token=claimed["delivery_token"],
        generation=claimed["generation"],
        outcome="PLAYBACK_INTENT",
        disposition=disposition,
    )
    assert started["delivery_status"] == "PLAYBACK_INTENT"
    # Test-only TTS process receipt; no actual audible endpoint is asserted.
    receipt = ledger.transition(
        UUID(claimed["request_id"]),
        household_id=situation["home"],
        client_id="isolated",
        token=claimed["delivery_token"],
        generation=claimed["generation"],
        outcome="DELIVERED",
        disposition=disposition,
        evidence={
            "playback_state": "DELIVERED",
            "timing_source": "LOCAL_PLAYBACK_PROCESS",
            "playback_completed_at": datetime.now(UTC).isoformat(),
            "actual_audible_start_at": None,
        },
    )
    assert receipt["delivery_status"] == "DELIVERED"


def test_core_vendor_handoff_current_binding_fault_then_idempotent_recovery(
    situation: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = compose(situation, monkeypatch)
    relay = uuid4()
    event = EventEnvelope.create(
        delivery_class=DeliveryClass.GUARANTEED,
        event_id=str(uuid4()),
        event_type="external.android.motion_reported",
        source=f"android-relay-report:{situation['home']}:{relay}",
        source_event_id=str(uuid4()),
        subject_key=f"resource/{situation['sensor']}",
        occurred_at=datetime.now(UTC),
        payload={
            "resource_id": str(situation["sensor"]),
            "format": "anima.android.motion.report.v1",
            "event_kind": "motion_reported",
            "source_package": "net.ajcloud.wansviewplus",
            "authority": "NONE",
        },
        metadata={
            "household_id": str(situation["home"]),
            "synthetic": False,
            "wake_eligible": True,
            "producer_qualified": True,
            "schema_qualification": "ANIMA_OWNED_SCHEMA",
            "producer_adapter": "isolated",
            "producer_version": "1",
            "external_content_trust": "EXTERNAL_UNTRUSTED",
        },
    )
    core.journal.append(event)
    with pytest.raises(ValueError, match="CANONICAL_HANDOFF_VENDOR_BINDING_UNAVAILABLE"):
        core.journal_event_watcher.recover_pending()
    assert core.journal_event_watcher.delivery_state == "HANDOFF_FAILED"
    source = VendorRelaySource(
        RelayRegistration(situation["home"], relay, {"fixture": situation["sensor"]}, frozenset()),
        "isolated-test-only-credential-32chars",
        enabled=True,
        official_app_ready=True,
        source_privacy_qualified=True,
        producer_adapter="isolated",
        producer_version="1",
        producer_qualified=True,
        wake_enabled=True,
    )
    monkeypatch.setattr(
        VendorRelayConfig, "from_environment", lambda: VendorRelayConfig(True, (source,))
    )
    assert core.journal_event_watcher.recover_pending() == 1
    assert core.journal_event_watcher.recover_pending() == 0
    with psycopg.connect(situation["url"]) as conn:
        assert conn.execute(
            "SELECT count(*) FROM anima_intelligence_requests "
            "WHERE household_id=%s AND causation_id=%s",
            (situation["home"], event.event_id),
        ).fetchone() == (1,)


def test_qualified_existing_connection_store_restores_frozen_ha_catalogue_not_live_readiness(
    situation: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    core = compose(situation, monkeypatch)
    monkeypatch.undo()
    for name in ("ANIMA_VENDOR_RELAY_CONFIG", "ANIMA_KNOWLEDGE_ROOT", "ANIMA_HOUSEHOLD_ID"):
        monkeypatch.delenv(name, raising=False)
    instance = str(uuid4())
    store = HAConnectionStore(tmp_path / "connection" / "home-assistant-credential.json")
    unit = (Path(__file__).parents[1] / "deploy/systemd/user/anima-core.service").read_text()
    assert (
        "Environment=ANIMA_HA_CONNECTION_FILE=%h/.config/anima/home-assistant-credential.json"
        in unit
    )
    monkeypatch.setenv("ANIMA_HA_CONNECTION_FILE", str(store.path))
    monkeypatch.setenv("ANIMA_HA_INSTANCE_ID", instance)
    monkeypatch.setenv("ANIMA_HA_PROVIDER_SCOPE", instance)
    monkeypatch.setenv("ANIMA_HA_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("ANIMA_HA_WEBSOCKET_URL", "ws://127.0.0.1:9/api/websocket")
    monkeypatch.setenv("ANIMA_SENTRY_HOUSEHOLD_ID", str(situation["home"]))
    monkeypatch.setenv("ANIMA_INTELLIGENCE_PROVIDER", "sentry")
    monkeypatch.setenv("HA_ACCESS_TOKEN", "")
    monkeypatch.setenv("ANIMA_HA_ACCESS_TOKEN", "")
    monkeypatch.setattr(HomeAssistantPlugin, "start", lambda self, secrets: None)
    missing = build_postgres_core(situation["url"])
    assert not store.path.exists()  # Composition must not seed a private credential.
    assert missing.home_assistant_adapter is None and missing.action_refresher is None
    assert missing.learning_service is not None
    assert (
        missing.learning_service.get_situation(situation["home"])["source_coverage"][
            "ha_bound_consumer"
        ]["status"]
        == "NOT_CONFIGURED"
    )
    store.save_new(
        {
            "version": 1,
            "token": "isolated-no-network",
            "user_id": "isolated",
            "instance_id": instance,
            "household_id": str(situation["home"]),
            "base_url": "http://127.0.0.1:9",
        }
    )
    connected = build_postgres_core(situation["url"])
    assert core.home_assistant_adapter is None
    assert connected.home_assistant_adapter is not None and connected.action_refresher is not None
    pending = IntelligenceRequestFactory.for_direct_sentry_interaction(
        sentry_request_id=str(uuid4()),
        household_id=situation["home"],
        source_surface="isolated",
        user_text="Isolated frozen tools",
        tools=connected.plugins.list_tools(),
        service_client_id="isolated",
    )
    catalogue = connected.sentry_boundary().catalogue(pending)
    ha_tools = [item for item in catalogue if item["plugin_id"] == "anima.provider.home-assistant"]
    assert ha_tools and all(item["availability"] for item in ha_tools)
    assert connected.home_assistant_adapter.status.health.value != "ONLINE"
    assert connected.learning_service is not None
    context = connected.learning_service.get_situation(situation["home"])
    assert context["source_coverage"]["ha_bound_consumer"]["coverage"] == "UNVERIFIED_NOT_QUIET"
    assert connected.plugins.secret_broker.resolve(("HA_ACCESS_TOKEN",)) == {
        "HA_ACCESS_TOKEN": "isolated-no-network"
    }
    monkeypatch.setenv("ANIMA_HA_INSTANCE_ID", str(uuid4()))
    with pytest.raises(HASetupError, match="HA_CONNECTION_CONFIGURATION_MISMATCH"):
        build_postgres_core(situation["url"])


def test_pc_core_searxng_composition_matches_existing_qualified_endpoint(
    situation: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path(__file__).parents[1]
    unit = (root / "deploy/systemd/user/anima-core.service").read_text()
    compose_text = (root / "compose.pc.yaml").read_text()
    assert "Environment=ANIMA_SEARXNG_URL=http://127.0.0.1:18888" in unit
    assert "Environment=ANIMA_SEARXNG_HOST=127.0.0.1" in unit
    assert "ANIMA_SEARXNG_URL: http://127.0.0.1:18888" in compose_text
    assert "ANIMA_SEARXNG_HOST: 127.0.0.1" in compose_text
    import anima_ha.ui_runtime as module

    factory = external_plugin
    bound: list[dict[str, Any]] = []

    def observed_factory(plugin_id: str, **kwargs: Any) -> Any:
        bound.append({"plugin_id": plugin_id, **kwargs})
        return factory(plugin_id, **kwargs)

    monkeypatch.setenv("ANIMA_SEARXNG_URL", "http://127.0.0.1:18888")
    monkeypatch.setenv("ANIMA_SEARXNG_HOST", "127.0.0.1")
    monkeypatch.setattr(module, "external_plugin", observed_factory)
    core = compose(situation, monkeypatch)
    assert bound and all(item["searxng_host"] == "127.0.0.1" for item in bound)
    request = IntelligenceRequestFactory.for_direct_sentry_interaction(
        sentry_request_id=str(uuid4()),
        household_id=situation["home"],
        source_surface="isolated",
        user_text="Isolated catalogue, no provider query",
        tools=core.plugins.list_tools(),
        service_client_id="isolated",
    )
    catalogue = core.sentry_boundary().catalogue(request)
    discovery = [item for item in catalogue if item["plugin_id"] == "anima.external.discovery"]
    assert discovery and all(item["availability"] for item in discovery)
    # This proves commissioned composition/frozen visibility, not successful
    # external search/network reachability or permission to issue a live query.


def test_android_readiness_fault_stale_quiet_and_malformed_are_distinct(tmp_path: Path) -> None:
    path = tmp_path / "diagnostic.json"
    now = datetime.now(UTC)
    value = {
        "state": "NOT_READY",
        "observed_at": now.isoformat(),
        "components": {"android_session": {"state": "BLOCKED", "reason": "BINDER_PERMISSION"}},
        "raw": "PRIVATE_SENTINEL",
    }
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    assert diagnostic_coverage(path, now=now)["last_access_fault"] == "BINDER_PERMISSION"
    stale = diagnostic_coverage(path, now=now + timedelta(seconds=91))
    assert stale["status"] == "NOT_READY" and stale["reason"] == "NO_FRESH_READINESS"
    value.update(state="READY", observed_at=now.isoformat(), components={})
    path.write_text(json.dumps(value))
    assert diagnostic_coverage(path, now=now)["status"] == "READY"
    assert "PRIVATE_SENTINEL" not in json.dumps(diagnostic_coverage(path, now=now))
