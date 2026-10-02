"""Exact mandatory alert source and unresolved/revoked real-store distinction."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from test_household_learning import config
from test_stage2_delivery_postgres import isolated_url as isolated_url
from test_stage3_household_situation import situation as situation
from test_stage6_owner_postgres import connected as connected

from anima_ha.alert_delivery import PostgresRequiredDelivery
from anima_ha.attention import AttentionProfile, SentryEventPath
from anima_ha.events import DeliveryClass, EventEnvelope
from anima_ha.intelligence import SentryAttentionBridge
from anima_ha.sentry_autowake import PostgresAutoWakeClaims
from anima_ha.sentry_service import CoreSentryHTTPService, SentryServicePrincipal
from anima_ha.sentry_voice_settings import SentryVoiceSettingsStore


@pytest.mark.parametrize(
    "case",
    [
        "nearby_over24",
        "context_unavailable",
        "name_unavailable",
        "explicit_never",
        "opa_unavailable",
        "sleep",
        *[
            f"receipt_{phase}_{case}"
            for phase in ("canonical", "followup")
            for case in (
                "busy",
                "empty",
                "explicit",
                "contradictory",
                "bad_unknown",
                "bad_completion",
                "local",
                "projection",
            )
        ],
    ],
)
def test_current_required_delivery_truth(
    connected: dict[str, Any], monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    core, home, person = connected["service"].core_runtime, connected["home"], connected["owner"]
    if core.journal_event_watcher is not None:
        core.journal_event_watcher.stop()
    learning = core.learning_service
    event_path = (
        SentryEventPath.ANNOUNCEMENT_AND_CONTEXTUAL_REASONING
        if case.startswith("receipt_followup_")
        else SentryEventPath.IMMEDIATE_ANNOUNCEMENT_ONLY
    )
    selected = {
        "resource_id": str(person),
        "mode": "ALWAYS",
        "sentry_path": event_path.value,
        "start_local": "00:00",
        "end_local": "23:59",
        "timezone": "America/New_York",
    }
    configured = learning.configure(home, person, config(device_notifications=[selected]))
    event = EventEnvelope.create(
        event_id=str(uuid4()),
        source_event_id=str(uuid4()),
        occurred_at=datetime.now(UTC) - timedelta(seconds=2),
        event_type="household.presence.connection_changed",
        source="anima.household_presence",
        subject_key=f"person/{person}",
        delivery_class=DeliveryClass.GUARANTEED,
        payload={
            "household_id": str(home),
            "person_id": str(person),
            "canonical_resource_id": str(person),
            "transition": "RECONNECTED",
            "is_authentication": False,
            "door_actor_verified": False,
        },
        metadata={"household_id": str(home)},
    )
    appended = core.journal.append(event)
    profile = AttentionProfile(f"stage8.alert:{event.event_id}", ())
    core.attention.prime_consumer_before(profile, event.event_id, appended.journal_position - 1)
    request = SentryAttentionBridge(
        attention=core.attention,
        context=core.context,
        store=core.intelligence_store,
        profile=profile,
        event_path_resolver=lambda *_: event_path,
    ).run_once(
        household_id=home,
        tools=[],
        consumer_name=event.event_id,
        limit=1,
        source_event_id=event.event_id,
    )[0]
    delivery = PostgresRequiredDelivery(connected["url"])
    voice = SentryVoiceSettingsStore(connected["url"])
    voice.update(home, {"sleep_enabled": False, "active_instance_id": "living_room"})
    service = CoreSentryHTTPService(
        core.sentry_boundary(), lambda: "unused-synthetic", voice_settings_store=voice
    )
    assert delivery.state(request.request_id)["state"] == "PENDING"
    assert service._alert_disposition(request)["required"], service._alert_disposition(request)
    if case == "nearby_over24":
        for _ in range(28):
            core.journal.append(
                EventEnvelope.create(
                    event_id=str(uuid4()),
                    source_event_id=str(uuid4()),
                    occurred_at=datetime.now(UTC),
                    event_type=event.event_type,
                    source=event.source,
                    subject_key=event.subject_key,
                    payload=event.payload,
                    metadata=event.metadata,
                    delivery_class=DeliveryClass.GUARANTEED,
                )
            )
        nearby = core.initiative_context.correlation_context(request)
        assert nearby["truncated"] and len(nearby["items"]) == 24
        assert event.event_id not in {item["event_id"] for item in nearby["items"]}
    elif case == "context_unavailable":
        monkeypatch.setattr(
            learning,
            "status",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("private failure")),
        )
    elif case == "name_unavailable":
        original = core.graph.get_node
        monkeypatch.setattr(
            core.graph,
            "get_node",
            lambda key: SimpleNamespace(name="") if key == person else original(key),
        )
    elif case == "explicit_never":
        learning.configure(
            home,
            person,
            config(
                expected_version=configured["config_version"],
                device_notifications=[
                    {**selected, "mode": "NEVER", "sentry_path": "NO_SENTRY_REASONING"}
                ],
            ),
        )
    elif case == "opa_unavailable":
        monkeypatch.setattr(
            core.policy_service.evaluator,
            "evaluate",
            lambda _: (_ for _ in ()).throw(RuntimeError("isolated OPA unavailable")),
        )
    elif case == "sleep":
        voice.update(home, {**voice.get(home), "sleep_enabled": True})
    response = delivery.next(
        household_id=home,
        client_id="isolated",
        not_before=datetime.now(UTC) - timedelta(seconds=30),
        disposition=service._alert_disposition,
        active_instance_id="living_room",
    )
    state = delivery.state(request.request_id)
    if case == "nearby_over24":
        assert response["status"] == "CLAIMED" and state["state"] == "CLAIMED"
    elif case.startswith("receipt_"):
        assert response["status"] == "CLAIMED", response
        service.required_delivery = delivery
        service.auto_wake_claims = PostgresAutoWakeClaims(
            connected["url"], enabled_at=datetime.now(UTC) - timedelta(seconds=30)
        )
        principal = SentryServicePrincipal.from_secret(
            client_id="isolated",
            household_id=home,
            provider_id="sentry",
            token="synthetic-required-receipt-only",
        )

        def record(claim: dict[str, Any], outcome: str, evidence: dict[str, Any]) -> dict[str, Any]:
            receipt = {
                key: claim[key]
                for key in (
                    "request_id",
                    "generation",
                    "delivery_token",
                    "active_instance_id",
                    "phase",
                )
            }
            return service.required_alert(
                {**receipt, "outcome": outcome, "evidence": evidence},
                principal,
                operation="receipt",
            )

        valid = {
            "playback_state": "DELIVERED",
            "timing_source": "LOCAL_PLAYBACK_PROCESS",
            "playback_process_started_at": "2026-10-02T12:00:00-04:00",
            "playback_completed_at": "2026-10-02T16:00:01Z",
            "actual_audible_start_at": None,
        }
        if case.startswith("receipt_followup_"):
            assert delivery.queue_followup(
                request.request_id, "Synthetic bounded follow-up.", service._alert_disposition
            )
            followup = delivery.state(request.request_id)["followup"]
            assert delivery.ready_followup(request.request_id, home, followup["response_digest"])
            assert record(response, "PLAYBACK_INTENT", {})["delivery_status"] == "PLAYBACK_INTENT"
            assert record(response, "DELIVERED", valid)["delivery_status"] == "DELIVERED"
            response = delivery.next(
                household_id=home,
                client_id="isolated",
                not_before=datetime.now(UTC) - timedelta(seconds=30),
                disposition=service._alert_disposition,
                active_instance_id="living_room",
            )
            assert response["phase"] == "FOLLOWUP" and response["status"] == "CLAIMED"
        suffix = case.split("_", 2)[2]
        if suffix != "busy":
            assert record(response, "PLAYBACK_INTENT", {})["delivery_status"] == "PLAYBACK_INTENT"
        if suffix in {"bad_unknown", "bad_completion"}:
            bad: dict[str, Any] = (
                {
                    "playback_state": "UNKNOWN",
                    "timing_source": "private prose",
                    "playback_process_started_at": {"nested": "prose"},
                }
                if suffix == "bad_unknown"
                else {**valid, "playback_completed_at": "private prose"}
            )
            before = delivery.state(request.request_id)
            with pytest.raises(ValueError, match="INVALID_PLAYBACK_EVIDENCE"):
                record(response, "UNKNOWN" if suffix == "bad_unknown" else "DELIVERED", bad)
            assert delivery.state(request.request_id) == before  # No durable update.
        elif suffix in {"local", "projection"}:
            if suffix == "projection":
                valid["timing_source"] = "PROJECTION_PLAYBACK_PROCESS"
            assert record(response, "DELIVERED", valid)["delivery_status"] == "DELIVERED"
        else:
            evidence = (
                {}
                if suffix in {"busy", "empty"}
                else {
                    "playback_state": "UNSTARTED",
                    "playback_process_started_at": None,
                    "playback_completed_at": None,
                    "timing_source": None,
                    "actual_audible_start_at": None,
                }
            )
            if suffix == "contradictory":
                evidence["playback_process_started_at"] = datetime.now(UTC).isoformat()
            result = record(response, "UNSTARTED", evidence)
            assert result["delivery_status"] == (
                "PENDING" if suffix in {"busy", "explicit"} else "UNKNOWN"
            )
        final = delivery.state(request.request_id)
        saved = final["followup"] if response["phase"] == "FOLLOWUP" else final
        if saved["state"] == "UNKNOWN":
            assert (
                delivery.next(
                    household_id=home,
                    client_id="isolated",
                    not_before=datetime.now(UTC) - timedelta(seconds=30),
                    disposition=service._alert_disposition,
                    active_instance_id="living_room",
                )["status"]
                == "EMPTY"
            )
        if response["phase"] == "FOLLOWUP":
            assert final["state"] == "DELIVERED"  # Follow-up cannot falsify canonical receipt.
    elif case == "explicit_never":
        assert response["status"] == "EMPTY" and state["state"] == "CANCELLED"
        assert state["reason"] == "CURRENT_POLICY_REVOKED"
    else:
        assert response["status"] == "EMPTY" and state["state"] == "PENDING"
        assert state["attempts"] == state["generation"] == 0
        assert state["reason"] == "CURRENT_AUTHORITY_OR_ANNOUNCEMENT_UNAVAILABLE"
    assert not connected["transport"].calls
    current = core.intelligence_store.get(request.request_id)
    assert current.attempt_count == 0 and not current.provider_invocation_started
