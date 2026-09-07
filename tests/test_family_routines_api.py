"""Session → CSRF → Core policy/plugin → governed Memory family-routine tests."""

from __future__ import annotations

import os
import threading
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from test_family_routines import Graph, Memory, fields
from test_sentry_household_spaces import Evaluator

from anima_ha.db.migrate import migrate
from anima_ha.family_routines import (
    FAMILY_ROUTINES_MANIFEST,
    FamilyRoutinesNativePlugin,
    family_routines_page,
)
from anima_ha.graph import (
    CanonicalRelationship,
    CommissioningDocument,
    PostgresHouseholdGraph,
    RelationshipType,
)
from anima_ha.intelligence import (
    IntelligenceLifecycle,
    IntelligenceOrigin,
    IntelligenceRequestFactory,
)
from anima_ha.memory import MemoryService, MemoryStatus
from anima_ha.plugins import ExecutionBoundary, NativeRuntime, PluginManager, ToolDescriptor
from anima_ha.policy import OpaPolicyClient, PolicyService, PostgresPolicyStore
from anima_ha.sentry_boundary import CoreSentryBoundary
from anima_ha.ui_api import DemoHouseholdReadModel, UIConfig, UIService, create_app
from anima_ha.ui_runtime import CoreUICommandGateway


def test_blocking_routine_reads_run_off_the_asgi_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Synchronous PostgreSQL/Graph work must not block SSE and other routes."""
    from fastapi import Request

    from anima_ha import family_routines_api

    graph, memory = Graph(), Memory()
    app = create_app(service_for(memory, graph, graph)[0])
    event_loop_threads: list[int] = []
    read_threads: list[int] = []
    original = family_routines_page

    @app.middleware("http")
    async def record_loop(request: Request, call_next: Any) -> Any:
        event_loop_threads.append(threading.get_ident())
        return await call_next(request)

    def recording_read(*args: Any, **kwargs: Any) -> dict[str, Any]:
        read_threads.append(threading.get_ident())
        result: dict[str, Any] = original(*args, **kwargs)
        return result

    monkeypatch.setattr(family_routines_api, "family_routines_page", recording_read)
    with TestClient(app) as client:
        client.get("/auth/login")
        assert client.get("/api/v1/family-routines").status_code == 200
    assert read_threads and not set(read_threads).intersection(event_loop_threads)


def service_for(memory: Any, graph: Any, fixture: Graph) -> tuple[UIService, Evaluator]:
    manager = PluginManager()
    manager.register(
        FAMILY_ROUTINES_MANIFEST, NativeRuntime(FamilyRoutinesNativePlugin(memory, graph))
    )
    manager.enable(FAMILY_ROUTINES_MANIFEST.plugin_id)
    evaluator = Evaluator("ALLOW")
    commands = CoreUICommandGateway(
        manager, PolicyService(evaluator), policy_role_resolver=lambda _: "owner"
    )
    read_model: Any = DemoHouseholdReadModel()
    read_model.memory_service = memory
    read_model.graph = graph
    service = UIService(
        config=UIConfig(test_auth_enabled=True),
        read_model=read_model,
        commands=cast(Any, commands),
        ha_user_map={"test-ha-user": (fixture.household.canonical_id, fixture.owner.canonical_id)},
    )
    return service, evaluator


def login(service: UIService) -> tuple[TestClient, dict[str, str]]:
    client = TestClient(create_app(service), follow_redirects=False)
    response = client.get("/auth/login")
    callback = client.get(response.headers["location"])
    assert callback.status_code == 307
    return client, {"Origin": "http://testserver", "X-Anima-CSRF": callback.headers["x-anima-csrf"]}


@pytest.mark.parametrize("durable", [False, True])
def test_save_reload_edit_disable_via_actual_api_and_core(durable: bool) -> None:
    fixture = Graph()
    memory: Any = Memory()
    graph: Any = fixture
    if durable:
        url = os.environ.get("ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL")
        if not url:
            pytest.skip("requires isolated ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL")
        with psycopg.connect(url) as connection:
            assert connection.execute("SELECT current_database()").fetchone() == (
                "anima_family_routines_test",
            )
        migrate(url, 5)
        graph = PostgresHouseholdGraph(url)
        graph.commission(
            CommissioningDocument(
                1,
                (fixture.household, fixture.owner, fixture.person, fixture.room),
                (
                    CanonicalRelationship(
                        uuid4(),
                        RelationshipType.MEMBER_OF,
                        fixture.owner.canonical_id,
                        fixture.household.canonical_id,
                    ),
                    CanonicalRelationship(
                        uuid4(),
                        RelationshipType.MEMBER_OF,
                        fixture.person.canonical_id,
                        fixture.household.canonical_id,
                    ),
                    CanonicalRelationship(
                        uuid4(),
                        RelationshipType.CONTAINS,
                        fixture.household.canonical_id,
                        fixture.room.canonical_id,
                    ),
                ),
            )
        )
        memory = MemoryService(url)
    service, evaluator = service_for(memory, graph, fixture)
    client, headers = login(service)
    empty = client.get("/api/v1/family-routines").json()
    assert empty["items"] == [] and empty["can_edit"] is True
    assert {item["person_id"] for item in empty["members"]} == {
        str(fixture.owner.canonical_id),
        str(fixture.person.canonical_id),
    }
    response = client.post(
        "/api/v1/family-routines/create", headers=headers, json={"payload": fields(fixture)}
    )
    assert response.status_code == 200 and response.json()["status"] == "SUCCEEDED"
    original = client.get("/api/v1/family-routines").json()["items"][0]
    assert original["person_id"] == str(fixture.person.canonical_id)
    # A newly built API/service view loads the same persisted records.
    reloaded_memory = memory
    if durable:
        assert url is not None
        reloaded_memory = MemoryService(url)
    fresh_service, _ = service_for(reloaded_memory, graph, fixture)
    refreshed, fresh_headers = login(fresh_service)
    assert refreshed.get("/api/v1/family-routines").json()["items"] == [original]
    response = refreshed.post(
        "/api/v1/family-routines/update",
        headers=fresh_headers,
        json={
            "payload": {
                **fields(fixture),
                "routine_id": original["routine_id"],
                "label": "Edited expectation",
            }
        },
    )
    assert response.json()["status"] == "SUCCEEDED"
    edited = refreshed.get("/api/v1/family-routines").json()["items"][0]
    assert edited["label"] == "Edited expectation" and edited["version"] != original["version"]
    response = refreshed.post(
        "/api/v1/family-routines/disable",
        headers=fresh_headers,
        json={"payload": {"routine_id": edited["routine_id"]}},
    )
    assert response.json()["status"] == "SUCCEEDED"
    disabled = refreshed.get("/api/v1/family-routines").json()["items"][0]
    assert disabled["enabled"] is False and disabled["version"] != edited["version"]
    stored = memory.get(UUID(original["routine_id"]))
    assert stored is not None and stored.status == MemoryStatus.SUPERSEDED
    assert evaluator.documents and evaluator.documents[0]["origin"] == "DIRECT_USER"


def test_api_authentication_csrf_and_policy_gate_before_memory_write() -> None:
    memory, graph = Memory(), Graph()
    service, evaluator = service_for(memory, graph, graph)
    unauthenticated = TestClient(create_app(service))
    assert unauthenticated.get("/api/v1/family-routines").status_code == 401
    client, headers = login(service)
    data = {"payload": fields(graph)}
    assert client.post("/api/v1/family-routines/create", json=data).status_code == 403
    assert (
        client.post(
            "/api/v1/family-routines/create",
            headers={**headers, "Origin": "https://foreign.invalid"},
            json=data,
        ).status_code
        == 403
    )
    assert not memory.records and not evaluator.documents
    evaluator.decision = "DENY"
    result = client.post("/api/v1/family-routines/create", headers=headers, json=data).json()
    assert result["status"] != "SUCCEEDED"
    assert not memory.records


def test_add_member_api_cannot_mint_identity_or_permissions() -> None:
    memory, graph = Memory(), Graph()
    service, evaluator = service_for(memory, graph, graph)
    client, headers = login(service)
    path = "/api/v1/family-routines/add-member"
    count = len(graph.members_of_household(graph.household.canonical_id))
    assert (
        client.post(path, json={"payload": {"name": "Synthetic added member"}}).status_code == 403
    )
    for forbidden in ("role", "semantic_role", "assurance", "principal_id", "household_id"):
        response = client.post(
            path,
            headers=headers,
            json={"payload": {"name": "Synthetic added member", forbidden: "owner"}},
        )
        assert response.status_code == 400 or response.json()["status"] != "SUCCEEDED"
    assert len(graph.members_of_household(graph.household.canonical_id)) == count
    evaluator.decision = "DENY"
    assert (
        client.post(
            path, headers=headers, json={"payload": {"name": "Synthetic added member"}}
        ).json()["status"]
        != "SUCCEEDED"
    )
    assert len(graph.members_of_household(graph.household.canonical_id)) == count
    evaluator.decision = "ALLOW"
    response = client.post(
        path, headers=headers, json={"payload": {"name": "Synthetic added member"}}
    )
    assert response.json()["status"] == "SUCCEEDED"
    options = client.get("/api/v1/family-routines").json()
    member = next(item for item in options["members"] if item["name"] == "Synthetic added member")
    node = graph.get_node(UUID(member["person_id"]))
    assert node is not None and "semantic_role" not in node.metadata
    assert not memory.records


def test_optin_real_opa_denial_keeps_routine_memory_unchanged() -> None:
    url = os.environ.get("ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL")
    opa = os.environ.get("ANIMA_FAMILY_ROUTINES_TEST_OPA_URL")
    if not url or not opa:
        pytest.skip("requires isolated routines PostgreSQL and OPA")
    with psycopg.connect(url) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "anima_family_routines_test",
        )
    migrate(url, 5)
    fixture = Graph()
    memory = MemoryService(url)
    service, _ = service_for(memory, fixture, fixture)
    commands = cast(CoreUICommandGateway, service.commands)
    commands.policy_service = PolicyService(
        OpaPolicyClient(opa), audit_store=PostgresPolicyStore(url)
    )
    commands.policy_role_resolver = lambda _: "guest"
    client, headers = login(service)
    response = client.post(
        "/api/v1/family-routines/create", headers=headers, json={"payload": fields(fixture)}
    )
    assert response.json()["status"] == "DENIED"
    with psycopg.connect(url) as connection:
        assert connection.execute(
            "SELECT count(*) FROM anima_memory_records WHERE household_id=%s",
            (fixture.household.canonical_id,),
        ).fetchone() == (0,)
        row = connection.execute(
            "SELECT count(*) FROM anima_policy_decisions WHERE household_id=%s",
            (fixture.household.canonical_id,),
        ).fetchone()
        assert row is not None and row[0] >= 1


@pytest.mark.parametrize(
    "key", ["person_id", "place_id", "household_id", "source_ref", "authority"]
)
def test_api_cannot_inject_foreign_scope_or_provenance(key: str) -> None:
    memory, graph = Memory(), Graph()
    client, headers = login(service_for(memory, graph, graph)[0])
    response = client.post(
        "/api/v1/family-routines/create",
        headers=headers,
        json={"payload": {**fields(graph), key: str(uuid4())}},
    )
    assert response.status_code in {200, 400}
    assert response.status_code == 400 or response.json()["status"] != "SUCCEEDED"
    assert not memory.records


def test_sentry_semantic_boundary_keeps_exact_native_source_and_policy() -> None:
    graph, memory = Graph(), Memory()
    manager = PluginManager()
    manager.register(
        FAMILY_ROUTINES_MANIFEST, NativeRuntime(FamilyRoutinesNativePlugin(memory, graph))
    )
    manager.enable(FAMILY_ROUTINES_MANIFEST.plugin_id)
    evaluator = Evaluator("ALLOW")
    request = IntelligenceRequestFactory.for_trigger(
        uuid4(),
        household_id=graph.household.canonical_id,
        origin=IntelligenceOrigin.DIRECT_SENTRY_INTERACTION,
        context_packet_id=uuid4(),
        context_digest="synthetic",
        tools=manager.list_tools(),
        provider_id="sentry",
        provider_version="1",
        principal_id=graph.owner.canonical_id,
    )
    request = replace(
        request,
        lifecycle=IntelligenceLifecycle.PROVIDER_RUNNING,
        claim_owner="synthetic",
        fencing_generation=1,
        provider_invocation_started=True,
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=2),
    )
    boundary = CoreSentryBoundary(
        manager, PolicyService(evaluator), cast(Any, SimpleNamespace(get=lambda _: request))
    )
    result = boundary.invoke_tool(request, "anima.family-routines.create_routine", fields(graph))
    assert result["status"] == "SUCCEEDED"
    listing = boundary.invoke_tool(request, "anima.family-routines.list_routines", {}, ordinal=2)
    assert len(listing["result"]["items"]) == 1
    for tool in FAMILY_ROUTINES_MANIFEST.tools:
        descriptor = ToolDescriptor.from_manifest(FAMILY_ROUTINES_MANIFEST, tool)
        assert descriptor.execution_boundary == (
            ExecutionBoundary.READ_ONLY
            if tool["name"] == "list_routines"
            else ExecutionBoundary.POLICY_GATED_INTERNAL
        )
        if tool["name"] != "list_routines":
            forged = replace(FAMILY_ROUTINES_MANIFEST, source="builtin:untrusted")
            assert (
                ToolDescriptor.from_manifest(forged, tool).execution_boundary
                == ExecutionBoundary.COORDINATED_CONSEQUENTIAL
            )
    evaluator.decision = "DENY"
    assert (
        boundary.invoke_tool(
            request, "anima.family-routines.create_routine", fields(graph), ordinal=3
        )["status"]
        != "SUCCEEDED"
    )
    assert len(memory.records) == 1
