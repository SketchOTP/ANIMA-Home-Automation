"""Verified originating Core replies via real current OPA and authenticated client."""

from __future__ import annotations

import os
import sys
import threading
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from test_stage2_delivery_postgres import isolated_url as isolated_url
from test_stage3_household_situation import situation as situation
from test_stage6_owner_postgres import connected as connected
from test_stage6_owner_postgres import frozen_request, saved_scene

from anima_ha.alert_delivery import PostgresRequiredDelivery
from anima_ha.approval_results import approval_presentation
from anima_ha.intelligence import (
    IntelligenceRequestFactory,
    IntelligenceResult,
    IntelligenceResultStatus,
)
from anima_ha.policy import ActionIntent, Assurance, Decision, IdentityContext, PolicyContext
from anima_ha.sentry_autowake import PostgresAutoWakeClaims
from anima_ha.sentry_service import (
    CoreSentryHTTPService,
    SentryServicePrincipal,
    _Handler,
    _UnixHTTPServer,
)
from anima_ha.sentry_voice_settings import SentryVoiceSettingsStore


def test_saved_scene_child_reply_never_continues_remaining_steps(
    connected: dict[str, Any],
) -> None:
    value, core = connected, connected["service"].core_runtime
    plugin = core.plugins.plugins["anima.provider.home-assistant"]
    tool = next(t for t in plugin.tools.values() if t.name == "set_power")
    tool = replace(tool, risk_class="EXTERNAL_SIDE_EFFECT")
    plugin.tools[tool.tool_id] = core.plugins.tools[tool.tool_id] = tool
    scene = saved_scene(value)
    boundary, request = frozen_request(value)
    result = boundary.invoke_tool(
        request,
        "anima.scenes.apply_scene",
        {"scene_id": scene["scene_id"], "expected_version": scene["version"]},
    )
    assert result["status"] == "REQUIRE_CONFIRMATION", result
    assert not value["transport"].calls
    approval = result["result"]["steps"][0]["result"]["approval_id"]
    assert boundary.submit_result(
        request,
        "isolated",
        IntelligenceResult(request.request_id, IntelligenceResultStatus.WAITING_CONFIRMATION),
    )
    decision = value["client"].post(
        f"/api/v1/approvals/{approval}",
        headers=value["headers"],
        json={"payload": {"decision": "APPROVE"}},
    )
    assert decision.status_code == 200, decision.text
    outcome = core.approval_results.outcome(request.request_id, value["home"], value["owner"])
    assert outcome["action_status"] == "SUCCEEDED" and outcome["result_status"] == "PARTIAL"
    assert outcome["scene_stopped"]
    reply = value["client"].get(f"/api/v1/conversation/{request.request_id}").json()
    assert "no remaining steps were started" in reply["response"]
    assert len(value["transport"].calls) == 1
    duplicate = value["client"].post(
        f"/api/v1/approvals/{approval}",
        headers=value["headers"],
        json={"payload": {"decision": "APPROVE"}},
    )
    assert duplicate.status_code == 409 and len(value["transport"].calls) == 1
    assert core.intelligence_store.get(request.request_id).attempt_count == 1


def test_current_stronger_auth_gate_is_not_owner_approval_or_dispatch(
    connected: dict[str, Any],
) -> None:
    value, core = connected, connected["service"].core_runtime
    # Actual current policy + fixed presentation; no invented unlock executor
    # or false relabelling of the supported power descriptor.
    decision = core.policy_service.evaluate(
        ActionIntent.create(
            household_id=value["home"], principal_id=value["owner"], semantic_action="unlock"
        ),
        IdentityContext(value["home"], value["owner"], Assurance.AUTHENTICATED),
        PolicyContext(principal_role="owner"),
    )
    assert decision.decision == Decision.REQUIRE_STRONGER_AUTH
    assert not value["transport"].calls
    presentation = approval_presentation(
        {
            "decision": "APPROVE",
            "action_status": "REQUIRE_STRONGER_AUTH",
            "result_status": "WAITING_STRONGER_AUTH",
        }
    )
    assert presentation["status"] == "WAITING_STRONGER_AUTH"
    assert "requires stronger authentication" in presentation["response"]


@pytest.fixture(autouse=True)
def explicit_sentry_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANIMA_INTELLIGENCE_PROVIDER", "sentry")


@pytest.mark.parametrize(
    "case",
    [
        "approved",
        "rejected",
        "current_tool_denied",
        "unknown",
        "busy",
        "lost_started",
        "expired",
        "foreign_client",
        "auto_opt_out",
        "resident",
        "resident_limited",
        "resident_denied",
        "current_role_revoked",
        "current_membership_revoked",
        "retired_edge",
        "retired_person",
        "retired_household",
        "intent_membership_revoked",
        "opa_unavailable",
        "post_intent_empty",
        "post_intent_contradictory",
        "post_intent_valid_unstarted",
        "bad_timing_source",
        "nested_timestamp",
        "bool_timestamp",
        "naive_timestamp",
        "malformed_timestamp",
        "bool_timing_source",
        "bool_playback_state",
        "valid_local_timing",
        "valid_projection_timing",
    ],
)
def test_native_current_verified_reply_has_no_execution_replay(
    connected: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    case: str,
) -> None:
    value, core = connected, connected["service"].core_runtime
    core.graph.update_person_profile(value["home"], value["owner"], access_level="UNRESTRICTED")
    plugin = core.plugins.plugins["anima.provider.home-assistant"]
    tool = next(t for t in plugin.tools.values() if t.name == "set_power")
    tool = replace(tool, risk_class="EXTERNAL_SIDE_EFFECT")
    plugin.tools[tool.tool_id] = core.plugins.tools[tool.tool_id] = tool
    client_id = "stage8-originating-native"
    pending = IntelligenceRequestFactory.for_direct_sentry_interaction(
        sentry_request_id=str(uuid4()),
        household_id=value["home"],
        principal_id=value["owner"],
        source_surface="always_on_voice",
        user_text="Synthetic direct recognized request.",
        tools=core.plugins.list_tools(),
        service_client_id=client_id,
        identity_context=IdentityContext(
            value["home"],
            value["owner"],
            Assurance.RECOGNIZED,
            explanation="Synthetic Core-issued recognized voice provenance, not owner UI auth",
        ).to_payload(),
    )
    store, boundary = core.intelligence_store, core.sentry_boundary()
    store.enqueue(pending)
    claimed = store.claim_specific(
        pending.request_id, client_id, household_id=value["home"], provider_id="sentry"
    )
    assert boundary.start_provider(claimed, client_id)
    request = store.get(pending.request_id)
    result = boundary.invoke_tool(
        request,
        tool.tool_id,
        {
            "resource_id": str(value["resources"][0]),
            "desired_on": True,
            "capability_id": str(
                core.graph.resource_capabilities(value["resources"][0])[0].canonical_id
            ),
        },
    )
    assert result["status"] == "REQUIRE_CONFIRMATION", result
    assert boundary.submit_result(
        request,
        client_id,
        IntelligenceResult(request.request_id, IntelligenceResultStatus.WAITING_CONFIRMATION),
    )
    if case in {"current_tool_denied", "resident_denied"}:
        tool = replace(tool, version="stage8-changed-descriptor")
        plugin.tools[tool.tool_id] = core.plugins.tools[tool.tool_id] = tool
    if case == "unknown":
        value["transport"].unknown_after = 1
    decision = "REJECT" if case == "rejected" else "APPROVE"
    response = value["client"].post(
        f"/api/v1/approvals/{result['result']['approval_id']}",
        headers=value["headers"],
        json={"payload": {"decision": decision}},
    )
    assert response.status_code == 200, response.text
    expected = (
        "POLICY_DENIED"
        if case in {"rejected", "current_tool_denied", "resident_denied"}
        else "UNKNOWN_RESULT"
        if case == "unknown"
        else "SUCCEEDED"
    )
    current = store.get(request.request_id)
    assert current.lifecycle.value in {"COMPLETED", "FAILED", "UNKNOWN_RESULT"}
    presented = value["client"].get(f"/api/v1/conversation/{request.request_id}").json()
    assert presented["available"], presented
    assert (
        core.approval_results.outcome(request.request_id, value["home"], value["owner"])[
            "action_status"
        ]
        == expected
    )
    calls = len(value["transport"].calls)
    assert calls == (0 if case in {"rejected", "current_tool_denied", "resident_denied"} else 1)
    if case in {"resident", "resident_limited", "resident_denied"}:
        core.graph.update_person_profile(
            value["home"],
            value["owner"],
            semantic_role="member",
            access_level="LIMITED" if case == "resident_limited" else "UNRESTRICTED",
        )
    if case == "current_role_revoked":
        core.graph.update_person_profile(value["home"], value["owner"], semantic_role="guest")
    if case == "current_membership_revoked":
        with psycopg.connect(value["url"]) as conn:
            conn.execute(
                "DELETE FROM anima_graph_relationships WHERE source_id=%s AND "
                "target_id=%s AND relationship_type='MEMBER_OF'",
                (value["owner"], value["home"]),
            )
    if case == "retired_edge":
        with psycopg.connect(value["url"]) as conn:
            conn.execute(
                "UPDATE anima_graph_relationships SET retired_at=now() WHERE source_id=%s "
                "AND target_id=%s AND relationship_type='MEMBER_OF'",
                (value["owner"], value["home"]),
            )
    if case in {"retired_person", "retired_household"}:
        with psycopg.connect(value["url"]) as conn:
            conn.execute(
                "UPDATE anima_graph_nodes SET retired_at=now() WHERE canonical_id=%s",
                (value["owner"] if case == "retired_person" else value["home"],),
            )
    path = Path(__file__).resolve().parents[1] / "integrations/sentry/anima-household"
    monkeypatch.syspath_prepend(str(path))
    from anima_household_client import AnimaHouseholdClient  # type: ignore[import-not-found]

    token = "stage8-synthetic-native-service-credential-not-owner"
    credential = tmp_path / "credential"
    credential.write_text(token)
    credential.chmod(0o600)
    principal = SentryServicePrincipal.from_secret(
        client_id=client_id, household_id=value["home"], provider_id="sentry", token=token
    )
    if case == "foreign_client":
        principal = replace(principal, client_id="different-stage8-client")
    voice = SentryVoiceSettingsStore(value["url"])
    voice.update(value["home"], {"sleep_enabled": False, "active_instance_id": "office"})
    service = CoreSentryHTTPService(
        boundary,
        lambda: token,
        service_principal=principal,
        voice_settings_store=voice,
        required_delivery=PostgresRequiredDelivery(value["url"]),
        auto_wake_claims=PostgresAutoWakeClaims(
            value["url"], enabled_at=datetime.now(UTC) - timedelta(seconds=30)
        ),
    )
    if case == "opa_unavailable":
        monkeypatch.setattr(
            core.policy_service.evaluator,
            "base_url",
            os.environ["ANIMA_STAGE3_TEST_OPA_URL"] + "/synthetic-missing-endpoint",
        )
    server = _UnixHTTPServer(str(tmp_path / "core.sock"), _Handler)
    server.service = service
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = AnimaHouseholdClient(str(tmp_path / "core.sock"), str(credential))
    try:
        native_source = os.environ.get("SENTRY_STAGE8_QUALIFICATION_SOURCE")
        if native_source and case in {
            "approved",
            "rejected",
            "current_tool_denied",
            "unknown",
            "auto_opt_out",
            "resident",
            "resident_limited",
            "resident_denied",
        }:
            from types import SimpleNamespace

            source_root = Path(native_source).resolve()
            monkeypatch.syspath_prepend(str(source_root))
            import importlib

            AnimaConfig = importlib.import_module("tools.sentry_anima").AnimaConfig
            AttentionQueueSource = importlib.import_module(
                "tools.sentry_anima_events"
            ).AttentionQueueSource

            assert Path(str(sys.modules["tools.sentry_anima_events"].__file__)).is_relative_to(
                source_root
            )
            monkeypatch.setattr(AnimaConfig, "load", lambda: SimpleNamespace(client=lambda: client))
            spoken: list[str] = []

            def playback(text: str) -> dict[str, Any]:
                spoken.append(text)
                return {
                    "delivered": True,
                    "playback_state": "DELIVERED",
                    "timing_source": "SYNTHETIC_CALLBACK",
                    "actual_audible_start_at": None,
                }

            source = AttentionQueueSource(
                object(),
                household_id=str(value["home"]),
                not_before=datetime.now(UTC) - timedelta(seconds=30),
                enabled=True,
                context_ready=True,
            )
            if case == "auto_opt_out":
                monkeypatch.setattr(
                    AnimaConfig,
                    "load",
                    lambda: SimpleNamespace(path="synthetic", client=lambda: client),
                )
                monkeypatch.setattr(
                    importlib.import_module("tools.sentry_anima"), "private_json", lambda _: {}
                )
                source = importlib.import_module(
                    "tools.sentry_anima_events"
                ).configured_attention_source(object())
                assert source()["gate"] == "AUTONOMOUS_NOT_ENABLED"
            speaker = SimpleNamespace(is_speaking=False, speak_with_timing=playback)
            delivered = source.deliver_required(speaker=speaker, active_instance_id="office")
            assert delivered["delivery_status"] == "DELIVERED", delivered
            assert len(spoken) == 1 and spoken[0] == presented["response"]
            assert (
                source.deliver_required(speaker=speaker, active_instance_id="office")["status"]
                == "EMPTY"
            )
            assert len(spoken) == 1 and len(value["transport"].calls) == calls
            evidence = core.approval_results.outcome(
                request.request_id, value["home"], value["owner"]
            )
            assert evidence["delivery_policy"]["assurance"] == "RECOGNIZED"
            assert evidence["delivery_policy"]["decision"] == "ALLOW"
            assert store.get(request.request_id).attempt_count == 1
            return
        if case == "expired":
            with psycopg.connect(value["url"]) as conn:
                conn.execute(
                    "UPDATE anima_intelligence_requests SET "
                    "result_metadata=jsonb_set(result_metadata,"
                    "'{approval_outcome,resolved_at}',%s::jsonb) WHERE request_id=%s",
                    (
                        '"' + (datetime.now(UTC) - timedelta(seconds=301)).isoformat() + '"',
                        request.request_id,
                    ),
                )
        claim = client.call("/v1/provider/approval-results/next", {"active_instance_id": "office"})
        if case in {
            "current_role_revoked",
            "current_membership_revoked",
            "retired_edge",
            "retired_person",
            "retired_household",
            "opa_unavailable",
        }:
            assert claim["status"] == "UNAVAILABLE", claim
            outcome = core.approval_results.outcome(
                request.request_id, value["home"], value["owner"]
            )
            assert (
                outcome["delivery"] == "PENDING" and outcome["delivery_reason"] == claim["reason"]
            )
            assert len(value["transport"].calls) == calls
            return
        if case in {"expired", "foreign_client"}:
            assert claim["status"] == "EMPTY", claim
            return
        assert claim["status"] == "CLAIMED" and claim["phase"] == "APPROVAL", claim
        receipt = {
            k: claim[k]
            for k in ("request_id", "generation", "delivery_token", "active_instance_id", "phase")
        }
        assert (
            client.call("/v1/provider/approval-results/next", {"active_instance_id": "office"})[
                "status"
            ]
            == "EMPTY"
        )
        if case == "busy":
            assert (
                client.call(
                    "/v1/provider/approval-results/receipt",
                    {**receipt, "outcome": "UNSTARTED", "evidence": {}},
                )["delivery_status"]
                == "PENDING"
            )
            return
        if case == "intent_membership_revoked":
            with psycopg.connect(value["url"]) as conn:
                conn.execute(
                    "UPDATE anima_graph_relationships SET retired_at=now() WHERE source_id=%s "
                    "AND target_id=%s AND relationship_type='MEMBER_OF'",
                    (value["owner"], value["home"]),
                )
            ack = client.call(
                "/v1/provider/approval-results/receipt",
                {**receipt, "outcome": "PLAYBACK_INTENT", "evidence": {}},
            )
            assert ack["status"] == "UNAVAILABLE" and ack["delivery_status"] == "CLAIMED"
            assert len(value["transport"].calls) == calls
            return
        ack = client.call(
            "/v1/provider/approval-results/receipt",
            {**receipt, "outcome": "PLAYBACK_INTENT", "evidence": {}},
        )
        assert ack["delivery_status"] == "PLAYBACK_INTENT"
        if case in {
            "bad_timing_source",
            "nested_timestamp",
            "bool_timestamp",
            "naive_timestamp",
            "malformed_timestamp",
            "bool_timing_source",
            "bool_playback_state",
        }:
            from anima_household_client import AnimaHouseholdError

            evidence = {"playback_state": "DELIVERED", "actual_audible_start_at": None}
            invalid_values: dict[str, dict[str, Any]] = {
                "bad_timing_source": {"timing_source": "arbitrary private prose"},
                "nested_timestamp": {"playback_process_started_at": {"private": "prose"}},
                "bool_timestamp": {"playback_completed_at": True},
                "naive_timestamp": {"playback_process_started_at": "2026-10-02T12:00:00"},
                "malformed_timestamp": {"playback_completed_at": "not a timestamp"},
                "bool_timing_source": {"timing_source": True},
                "bool_playback_state": {"playback_state": True},
            }
            evidence.update(invalid_values[case])
            before = core.approval_results.outcome(
                request.request_id, value["home"], value["owner"]
            )
            with pytest.raises(AnimaHouseholdError):
                client.call(
                    "/v1/provider/approval-results/receipt",
                    {
                        **receipt,
                        "outcome": "DELIVERED",
                        "evidence": evidence,
                    },
                )
            assert (
                core.approval_results.outcome(request.request_id, value["home"], value["owner"])
                == before
            )
            assert len(value["transport"].calls) == calls
            return
        if case.startswith("post_intent_"):
            evidence = (
                {}
                if case == "post_intent_empty"
                else {
                    "playback_state": "UNSTARTED",
                    "playback_process_started_at": None,
                    "actual_audible_start_at": None,
                    "timing_source": None,
                }
            )
            if case == "post_intent_contradictory":
                evidence["playback_process_started_at"] = datetime.now(UTC).isoformat()
            ack = client.call(
                "/v1/provider/approval-results/receipt",
                {**receipt, "outcome": "UNSTARTED", "evidence": evidence},
            )
            retryable = case == "post_intent_valid_unstarted"
            assert ack["delivery_status"] == ("PENDING" if retryable else "UNKNOWN")
            reclaimed = client.call(
                "/v1/provider/approval-results/next", {"active_instance_id": "office"}
            )
            assert reclaimed["status"] == ("CLAIMED" if retryable else "EMPTY")
            assert (
                len(value["transport"].calls) == calls
                and store.get(request.request_id).attempt_count == 1
            )
            return
        if case == "lost_started":
            with psycopg.connect(value["url"]) as conn:
                conn.execute(
                    "UPDATE anima_intelligence_requests SET "
                    "result_metadata=jsonb_set(result_metadata,"
                    "'{approval_outcome,delivery_lease_until}',%s::jsonb) WHERE request_id=%s",
                    (
                        '"' + (datetime.now(UTC) - timedelta(seconds=1)).isoformat() + '"',
                        request.request_id,
                    ),
                )
            assert (
                client.call("/v1/provider/approval-results/next", {"active_instance_id": "office"})[
                    "status"
                ]
                == "EMPTY"
            )
            assert (
                core.approval_results.outcome(request.request_id, value["home"], value["owner"])[
                    "delivery"
                ]
                == "UNKNOWN"
            )
            return
        # Actual client receives fixed Core prose for mock playback, then
        # reports only playback-owned timing. No acoustic/human proof claimed.
        spoken = [claim["announcement"]["text"]]
        callback = {
            "playback_state": "DELIVERED",
            "timing_source": "SYNTHETIC_CALLBACK",
            "actual_audible_start_at": None,
        }
        if case in {"valid_local_timing", "valid_projection_timing"}:
            callback.update(
                timing_source=(
                    "LOCAL_PLAYBACK_PROCESS"
                    if case == "valid_local_timing"
                    else "PROJECTION_PLAYBACK_PROCESS"
                ),
                playback_process_started_at="2026-10-02T12:00:00-04:00",
                playback_completed_at="2026-10-02T16:00:01Z",
            )
        ack = client.call(
            "/v1/provider/approval-results/receipt",
            {
                **receipt,
                "outcome": "DELIVERED",
                "evidence": callback,
            },
        )
        assert ack["delivery_status"] == "DELIVERED" and len(spoken) == 1
        assert (
            client.call("/v1/provider/approval-results/next", {"active_instance_id": "office"})[
                "status"
            ]
            == "EMPTY"
        )
        assert len(value["transport"].calls) == calls
        assert store.get(request.request_id).attempt_count == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
