"""Evidence for the commissioned Phase 12 production composition.

This target uses the real PostgreSQL graph, journal, attention, context,
plugin, task, calendar, and OPA boundaries. The model response is the only
scripted seam. It intentionally does not require a live HA instance; absent HA
commissioning is reported as an explicit capability gate.
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from anima_ha.agent import CodexTurnResult, FinalDecision, ScriptedCodexAdapter, TokenUsage
from anima_ha.calendar import CalendarStatus
from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.fixtures import sample_household_document
from anima_ha.graph import NodeKind, PostgresHouseholdGraph, ProviderReference
from anima_ha.ui_api import PostgresHouseholdReadModel, UIConfig, UIService
from anima_ha.ui_runtime import build_postgres_core

DATABASE_URL = os.environ.get(
    "ANIMA_DATABASE_URL", "postgresql://anima:anima_dev_only@localhost:55432/anima"
)
OPA_URL = os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181")
HA_SCOPE = os.environ.get("ANIMA_HA_PROVIDER_SCOPE", "phase12-commissioned-runtime")
HA_USER_ID = "phase12-commissioned-ha-user"


def main() -> int:
    os.environ["ANIMA_HA_PROVIDER_SCOPE"] = HA_SCOPE
    graph = PostgresHouseholdGraph(DATABASE_URL)
    document = sample_household_document()
    graph.commission(document)
    household = next(node for node in document.nodes if node.kind == NodeKind.HOUSEHOLD)
    person = next(node for node in document.nodes if node.name == "Alex")
    graph.map_provider_reference(
        ProviderReference(
            uuid5(NAMESPACE_URL, f"anima:phase12:user:{HA_SCOPE}:{HA_USER_ID}"),
            "home_assistant",
            HA_SCOPE,
            "user",
            HA_USER_ID,
            person.canonical_id,
        ),
        allow_remap=True,
    )

    core = build_postgres_core(
        DATABASE_URL,
        opa_url=OPA_URL,
        codex=ScriptedCodexAdapter(
            [
                CodexTurnResult(
                    FinalDecision("DONE", True, "The commissioned runtime is connected.", "done"),
                    TokenUsage(),
                    1.0,
                    ("turn.completed",),
                )
            ]
        ),
    )
    service = UIService(
        config=UIConfig(test_auth_enabled=False),
        core_runtime=core,
        read_model=PostgresHouseholdReadModel(
            DATABASE_URL,
            graph=core.graph,
            truth=core.truth.projection,
            plugins=core.plugins,
        ),
        identity_resolver=core.identity_resolver,
    )
    identity = service.map_ha_user(HA_USER_ID)
    events = service.events
    commands = core.commands(events)

    schedule = {
        "kind": "ONCE",
        "timezone": "UTC",
        "run_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    task = commands.task_mutation(
        identity,
        "schedule",
        {
            "task_type": "REASONING_DUE",
            "title": f"Phase 12 runtime proof {uuid5(NAMESPACE_URL, HA_USER_ID)}",
            "payload": {"objective": "commissioned runtime evidence"},
            "schedule": schedule,
        },
    )
    if task.get("status") != "SUCCEEDED":
        raise AssertionError(f"real OPA task mutation failed: {task}")

    calendar = commands.calendar_mutation(
        identity,
        "create_event",
        {
            "title": "Phase 12 runtime proof",
            "start_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
            "end_at": (datetime.now(UTC) + timedelta(hours=2, minutes=30)).isoformat(),
            "timezone": "UTC",
        },
    )
    if calendar.get("status") != "SUCCEEDED":
        raise AssertionError(f"real OPA calendar mutation failed: {calendar}")

    pipeline = core.conversation(events)
    core.attention.register_profile(pipeline.profile)
    event_id = str(uuid5(NAMESPACE_URL, f"phase12:user-request:{time.time_ns()}"))
    event = EventEnvelope.create(
        event_id=event_id,
        event_type="user.request",
        source="anima.ui",
        subject_key=f"household/{household.canonical_id}",
        occurred_at=datetime.now(UTC),
        payload={"text": "Connect to the commissioned runtime."},
        importance=EventImportance.IMPORTANT,
        delivery_class=DeliveryClass.GUARANTEED,
        correlation_id=event_id,
        metadata={
            "household_id": str(household.canonical_id),
            "principal_id": str(person.canonical_id),
            "origin": "DIRECT_USER",
        },
    )
    core.journal.append(event)
    conversation = pipeline.run(identity, event)
    if conversation["response"] != "The commissioned runtime is connected.":
        raise AssertionError(conversation)

    read_model = service.read_model
    assert isinstance(read_model, PostgresHouseholdReadModel)
    home = read_model.home(identity)
    capabilities = read_model.capabilities(identity)
    plugin_ids = [plugin.manifest.plugin_id for plugin in core.plugins.list_plugins()]
    assert "anima.external.shopping.upcitemdb" in plugin_ids
    assert "anima.external.shopping" not in plugin_ids
    assert "anima.external.shopping.bestbuy" not in plugin_ids
    assert "anima.provider.home-assistant" not in plugin_ids

    output = {
        "identity_mapping": "EXACT_ONE_COMMISSIONED_PERSON_TO_HOUSEHOLD",
        "household_id": str(identity.household_id),
        "principal_id": str(identity.principal_id),
        "real_opa_task": task["status"],
        "real_opa_calendar": calendar["status"],
        "task_status": task.get("result", {}).get("task", {}).get("status"),
        "calendar_status": calendar.get("result", {}).get("event", {}).get("status"),
        "conversation_trace": conversation["trace"],
        "home_household": home["household"],
        "home_presence": home["presence"],
        "capability_ids": [str(item["id"]) for item in capabilities],
        "active_plugins": plugin_ids,
        "ha_capability": "EXTERNAL_RESOURCE_GATE_HA_COMMISSIONING",
        "calendar_cancel_status_enum": CalendarStatus.ACTIVE.value,
        "phase13": False,
    }
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
