"""Current restricted PG/OPA, recognized direct caller and scripted audio only."""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from test_stage2_delivery_postgres import isolated_url as isolated_url
from test_stage3_household_situation import situation as situation
from test_stage6_owner_postgres import connected as connected

from anima_ha.action import ActionStatus
from anima_ha.intelligence import IntelligenceOrigin
from anima_ha.policy import Assurance, IdentityContext
from anima_ha.sentry_boundary import SentryBoundaryError
from anima_ha.sentry_voice_settings import SentryControlNativePlugin


def request(value: dict[str, Any]) -> tuple[Any, Any, list[Any]]:
    core = value["service"].core_runtime
    calls: list[Any] = []

    class Audio:
        def audio(self, operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
            calls.append((operation, arguments))
            return (
                {"audio_output": arguments.get("output", "usb")}
                if "projection" in operation
                else {"percent": 55.0, "muted": False}
            )

    core.plugins.plugins["anima.sentry-control"].runtime.plugin.audio_client = Audio()
    core.graph.update_person_profile(value["home"], value["owner"], access_level="UNRESTRICTED")
    boundary = core.sentry_boundary()
    pending = boundary.create_direct_request(
        household_id=value["home"],
        principal_id=value["owner"],
        sentry_request_id=str(uuid4()),
        source_surface="always_on_voice",
        user_text="Synthetic audio request",
        identity_context=IdentityContext(value["home"], value["owner"], Assurance.RECOGNIZED),
    )
    claimed = core.intelligence_store.claim_specific(
        pending.request_id, "stage9", household_id=value["home"], provider_id="sentry"
    )
    assert claimed and boundary.start_provider(claimed, "stage9")
    return boundary, core.intelligence_store.get(pending.request_id), calls


def test_all_six_recognized_direct_core_controls(connected: dict[str, Any]) -> None:
    boundary, current, calls = request(connected)
    for ordinal, (name, args) in enumerate(
        (
            ("get_system_volume", {}),
            ("set_system_volume", {"percent": 50}),
            ("adjust_system_volume", {"delta_percent": 5}),
            ("set_system_muted", {"muted": True}),
            ("get_projection_audio_output", {}),
            ("set_projection_audio_output", {"output": "usb"}),
            ("set_projection_audio_output", {"output": "hdmi"}),
        ),
        1,
    ):
        outcome = boundary.invoke_tool(
            current, f"anima.sentry-control.{name}", args, ordinal=ordinal
        )
        assert outcome["status"] == "SUCCEEDED", outcome
        assert outcome["result"]["result"]
    assert len(calls) == 7
    assert (
        current.request_metadata["direct_context"]["identity_context"]["assurance"] == "RECOGNIZED"
    )


def test_limited_reads_survive_writes_and_autonomous_are_denied(connected: dict[str, Any]) -> None:
    boundary, current, calls = request(connected)
    connected["service"].core_runtime.graph.update_person_profile(
        connected["home"], connected["owner"], access_level="LIMITED"
    )
    assert (
        boundary.invoke_tool(current, "anima.sentry-control.get_system_volume", {})["status"]
        == "SUCCEEDED"
    )
    assert (
        boundary.invoke_tool(current, "anima.sentry-control.set_system_volume", {"percent": 50})[
            "reason"
        ]
        == "USER_ACCESS_LIMITED"
    )
    assert (
        boundary.invoke_tool(
            replace(current, origin=IntelligenceOrigin.AUTONOMOUS_ATTENTION),
            "anima.sentry-control.get_system_volume",
            {},
        )["reason"]
        == "DIRECT_OPERATOR_REQUIRED"
    )
    assert len(calls) == 1


def test_invalid_arguments_and_current_membership_revocation_zero_dispatch(
    connected: dict[str, Any],
) -> None:
    boundary, current, calls = request(connected)
    assert (
        boundary.invoke_tool(current, "anima.sentry-control.set_system_muted", {"muted": "true"})[
            "status"
        ]
        != "SUCCEEDED"
    )
    with psycopg.connect(connected["url"]) as conn:
        conn.execute(
            "UPDATE anima_graph_relationships SET retired_at=now() "
            "WHERE source_id=%s AND target_id=%s AND relationship_type='MEMBER_OF'",
            (connected["owner"], connected["home"]),
        )
    assert (
        boundary.invoke_tool(current, "anima.sentry-control.set_system_volume", {"percent": 50})[
            "status"
        ]
        != "SUCCEEDED"
    )
    assert calls == []


def test_recognized_voice_cannot_authorize_enrollment(connected: dict[str, Any]) -> None:
    boundary, current, calls = request(connected)
    result = boundary.invoke_tool(
        current,
        "anima.household-users.authorize_face_profile",
        {"person_id": str(connected["member"]), "action": "start"},
    )
    assert result["status"] != "SUCCEEDED", result
    assert calls == []


def test_relative_adjustment_duplicate_loss_restart_conflict_and_stale(
    connected: dict[str, Any],
) -> None:
    boundary, current, calls = request(connected)
    core = connected["service"].core_runtime
    runtime = core.plugins.plugins["anima.sentry-control"].runtime
    plugin = runtime.plugin
    tool = "anima.sentry-control.adjust_system_volume"
    first = boundary.invoke_tool(current, tool, {"delta_percent": 5}, ordinal=1)
    assert first["status"] == "SUCCEEDED", first
    assert boundary.invoke_tool(current, tool, {"delta_percent": 5}, ordinal=1) == first
    assert len(calls) == 1
    conflict = boundary.invoke_tool(current, tool, {"delta_percent": 10}, ordinal=1)
    assert conflict["status"] != "SUCCEEDED", conflict
    assert len(calls) == 1

    class LostResult:
        def audio(self, operation: str, args: dict[str, Any]) -> dict[str, Any]:
            calls.append((operation, args))  # host increment happened
            # A concurrent identical call while HTTP is outstanding cannot own it.
            pending = boundary.invoke_tool(current, tool, args, ordinal=2)
            assert pending["status"] == "UNKNOWN_RESULT", pending
            raise TimeoutError("synthetic result lost after host effect")

    plugin.audio_client = LostResult()
    lost = boundary.invoke_tool(current, tool, {"delta_percent": 5}, ordinal=2)
    assert lost["status"] == "UNKNOWN_RESULT", lost
    assert len(calls) == 2
    # Reconstruct the production native plugin against the same existing ledger.
    runtime.plugin = SentryControlNativePlugin(
        plugin.store, plugin.audio_client, plugin.principal_is_current, plugin.action_store
    )
    assert boundary.invoke_tool(current, tool, {"delta_percent": 5}, ordinal=2) == lost
    assert len(calls) == 2
    with psycopg.connect(connected["url"]) as conn:
        rows = conn.execute(
            "SELECT status FROM anima_actions WHERE tool_id=%s AND household_id=%s "
            "ORDER BY created_at",
            (tool, connected["home"]),
        ).fetchall()
    assert [row[0] for row in rows] == ["SUCCEEDED", "UNKNOWN_RESULT"]

    # Crash/restart after EXECUTING is durably committed cannot replay either.
    assert plugin.action_store is not None
    with psycopg.connect(connected["url"]) as conn:
        conn.execute(
            "UPDATE anima_actions SET status='EXECUTING' "
            "WHERE tool_id=%s AND household_id=%s AND status='UNKNOWN_RESULT'",
            (tool, connected["home"]),
        )
    recovered = plugin.action_store.recover_incomplete()
    assert any(
        row.tool_id == tool and row.status == ActionStatus.UNKNOWN_RESULT for row in recovered
    )
    assert (
        boundary.invoke_tool(current, tool, {"delta_percent": 5}, ordinal=2)["status"]
        == "UNKNOWN_RESULT"
    )
    assert len(calls) == 2
    # A stale worker must not receive success or start another host effect.
    with pytest.raises(SentryBoundaryError, match="INTELLIGENCE_CLAIM_LOST"):
        boundary.invoke_tool(
            replace(current, fencing_generation=current.fencing_generation + 1),
            tool,
            {"delta_percent": 5},
            ordinal=1,
        )
    assert len(calls) == 2
