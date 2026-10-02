"""Opt-in two-source qualification of the actual resident task/playback consumer.

All model calls are synthetic runner invocations with temporary authority and
workspace, HTTP weather is mocked, and no physical speaker is instantiated.
"""

from __future__ import annotations

import importlib
import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from test_stage2_delivery_postgres import isolated_url as isolated_url
from test_stage3_household_situation import situation as situation
from test_stage6_owner_postgres import connected as connected
from test_stage8_owner_postgres import commissioned_weather as commissioned_weather
from test_stage8_task_result_postgres import due_task, request_for

from anima_ha.sentry_autowake import PostgresAutoWakeClaims
from anima_ha.sentry_service import (
    CoreSentryHTTPService,
    SentryServicePrincipal,
    _Handler,
    _UnixHTTPServer,
)


@pytest.fixture(autouse=True)
def explicit_sentry_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANIMA_INTELLIGENCE_PROVIDER", "sentry")


@pytest.mark.parametrize("case", ["delivered", "unavailable", "ambiguous"])
def test_saved_task_actual_resident_consumer_without_autonomous_opt_in(
    commissioned_weather: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path, case: str
) -> None:
    source_root = os.environ.get("SENTRY_STAGE8_QUALIFICATION_SOURCE")
    if not source_root:
        pytest.skip("explicit second-source resident qualification required")
    monkeypatch.syspath_prepend(str(Path(source_root).resolve()))
    # Reuse the existing fully temporary resident/profile/authority fixture;
    # do not read an installed resident profile or launch its actual provider.
    fixture_module = importlib.import_module("tests.test_sentry_anima_resident_events")
    assert Path(str(fixture_module.__file__)).is_relative_to(Path(source_root).resolve())
    fixture = fixture_module.ResidentEventIntegrationTests()
    fixture.setUp()
    value, core = commissioned_weather, commissioned_weather["service"].core_runtime
    task = due_task(value)
    assert core.owner_task_results.run_once()["dispatched"] == 1
    request = request_for(value, task)
    assert any(t["tool_id"] == "anima.external.weather.get" for t in request.catalogue)
    paths = Path(__file__).resolve().parents[1] / "integrations/sentry/anima-household"
    monkeypatch.syspath_prepend(str(paths))
    client_class = importlib.import_module("anima_household_client").AnimaHouseholdClient
    calls = value["weather_calls"]
    token = "stage8-synthetic-native-task-client"
    credential = tmp_path / "credential"
    credential.write_text(token)
    credential.chmod(0o600)
    service = CoreSentryHTTPService(
        core.sentry_boundary(),
        lambda: token,
        service_principal=SentryServicePrincipal.from_secret(
            client_id="stage8-task-voice",
            household_id=value["home"],
            provider_id="sentry",
            token=token,
        ),
        auto_wake_claims=PostgresAutoWakeClaims(value["url"], enabled_at=None),
    )
    server = _UnixHTTPServer(str(tmp_path / "core.sock"), _Handler)
    server.service = service
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = client_class(str(tmp_path / "core.sock"), str(credential))
    config_module = importlib.import_module("tools.sentry_anima")
    events_module = importlib.import_module("tools.sentry_anima_events")
    model_calls: list[str] = []
    spoken: list[str] = []

    def scripted_model(*args: Any, **kwargs: Any) -> Any:
        model_calls.append("synthetic resident turn")
        bound = Path(kwargs["env"]["ANIMA_PREBOUND_FILE"])
        binding = json.loads(bound.read_text())
        actual = client.invoke(
            binding["request_id"],
            binding["binding"],
            "anima.external.weather.get",
            {"latitude": 40.0, "longitude": -74.0},
            ordinal=1,
        )
        assert actual["status"] == "SUCCEEDED", actual
        bound.with_name("metadata.json").write_text(
            json.dumps({"version": 1, "status": "SUCCEEDED", "calls": 1})
        )
        final = {
            "decision": "speak",
            "answer": "Current synthetic weather is 21.5 degrees.",
            "status": "completed",
            "local_fact_ids": [],
            "limitations": [],
        }
        return SimpleNamespace(
            returncode=0,
            stderr="",
            stdout="\n".join(
                [
                    json.dumps({"type": "thread.started", "thread_id": fixture.thread_id}),
                    json.dumps(
                        {
                            "type": "item.completed",
                            "item": {"type": "agent_message", "text": json.dumps(final)},
                        }
                    ),
                ]
            ),
        )

    def playback(text: str) -> dict[str, Any]:
        spoken.append(text)
        return {
            "delivered": case == "delivered",
            "playback_state": "DELIVERED" if case == "delivered" else "UNKNOWN",
            "timing_source": "SYNTHETIC_PLAYBACK_CALLBACK",
            "actual_audible_start_at": None,
        }

    speaker = SimpleNamespace(is_speaking=False, speak_with_timing=playback)
    if case == "unavailable":
        speaker = SimpleNamespace(is_speaking=False)
    settings = json.loads(fixture.config.read_text())
    settings["auto_wake"] = {
        "enabled": False,
        "context_ready": True,
        "household_id": str(value["home"]),
    }
    fixture.config.write_text(json.dumps(settings))
    try:
        with (
            patch.object(config_module.AnimaConfig, "client", return_value=client),
            patch.object(events_module, "_event_process", side_effect=scripted_model),
        ):
            source = events_module.configured_attention_source(fixture.agent)
            assert not source.enabled and source.owner_tasks_enabled
            assert source._filters() == {"origin": "DURABLE_TASK"}
            result = source(speaker=speaker)
            assert result["status"] == "RECORDED", result
            assert (
                result["delivery_status"]
                == {"delivered": "DELIVERED", "unavailable": "UNAVAILABLE", "ambiguous": "UNKNOWN"}[
                    case
                ]
            ), result
            assert result["initiative_reason"] == "EXPLICIT_OWNER_TASK"
            assert len(calls) == 1 and len(model_calls) == 1
            assert len(spoken) == (0 if case == "unavailable" else 1)
            if spoken:
                assert spoken == ["Current synthetic weather is 21.5 degrees."]
                assert result["playback_evidence"]["actual_audible_start_at"] is None
            current = core.intelligence_store.get(request.request_id)
            assert current.lifecycle.value == "COMPLETED" and current.attempt_count == 1
            assert source(speaker=speaker)["status"] == "EMPTY"
            assert len(model_calls) == 1 and len(calls) == 1
            assert service.auto_wake_claims is not None
            with pytest.raises(ValueError, match="not commissioned"):
                service.auto_wake_claims.window(
                    {
                        "origin": "AUTONOMOUS_ATTENTION",
                        "not_before": datetime.now(UTC).isoformat(),
                        "max_age_seconds": 120,
                    }
                )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        fixture.doCleanups()
