"""Production HTTP/Core routes; fixture policy is NOT real OPA authorization.

Optional PostgreSQL/OPA tests use only the dedicated routines test database.
No owner data, external delivery, SENTRY model or production service is used.
"""

from __future__ import annotations

import os
import threading
from dataclasses import replace
from typing import Any, cast
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from test_family_routines import Graph
from test_family_routines_api import login, service_for
from test_preferences import FakeMemoryService

from anima_ha.db.migrate import migrate
from anima_ha.graph import (
    CanonicalRelationship,
    CommissioningDocument,
    PostgresHouseholdGraph,
    RelationshipType,
)
from anima_ha.memory import MemoryService, MemoryStatus
from anima_ha.plugins import NativeRuntime
from anima_ha.policy import OpaPolicyClient, PolicyService, PostgresPolicyStore
from anima_ha.preferences import PREFERENCES_MANIFEST, PreferencesNativePlugin, preferences_page
from anima_ha.ui_api import UIService, create_app
from anima_ha.ui_runtime import CoreUICommandGateway

PATH = "/api/v1/preferences"


def preferences_service(memory: Any, graph: Any, fixture: Graph) -> tuple[UIService, Any]:
    service, evaluator = service_for(memory, graph, fixture)
    commands = cast(CoreUICommandGateway, service.commands)
    commands.manager.register(
        PREFERENCES_MANIFEST, NativeRuntime(PreferencesNativePlugin(memory, graph))
    )
    commands.manager.enable(PREFERENCES_MANIFEST.plugin_id)
    return service, evaluator


def prepared(durable: bool = False) -> tuple[Any, Any, Graph, str | None]:
    fixture = Graph()
    if not durable:
        return FakeMemoryService(), fixture, fixture, None
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
    return MemoryService(url, index_enabled=False), graph, fixture, url


def mutate(
    client: TestClient, headers: dict[str, str], operation: str, payload: dict[str, Any]
) -> Any:
    return client.post(f"{PATH}/{operation}", headers=headers, json={"payload": payload})


def rejected(response: Any) -> None:
    assert response.status_code in {200, 400}
    assert response.status_code == 400 or response.json()["status"] != "SUCCEEDED"


@pytest.mark.parametrize("durable", [False, True])
def test_shared_personal_create_filter_reload_update_retract_through_core(durable: bool) -> None:
    memory, graph, fixture, url = prepared(durable)
    service, evaluator = preferences_service(memory, graph, fixture)
    client, headers = login(service)
    empty = client.get(PATH).json()
    assert empty["items"] == [] and empty["next_cursor"] is None and empty["can_edit"] is True
    assert {item["person_id"] for item in empty["members"]} == {
        str(fixture.owner.canonical_id),
        str(fixture.person.canonical_id),
    }
    for payload in (
        {"content": "Synthetic household default", "category": "notifications", "person_id": None},
        {
            "content": "Synthetic personal exception",
            "category": "notifications",
            "person_id": str(fixture.person.canonical_id),
        },
    ):
        response = mutate(client, headers, "create", payload)
        assert response.status_code == 200 and response.json()["status"] == "SUCCEEDED"
    items = client.get(PATH).json()["items"]
    shared = next(item for item in items if item["scope"] == "household")
    personal = next(item for item in items if item["scope"] == "personal")
    assert shared["person_id"] is None
    assert personal["person_name"] == fixture.person.name
    assert shared["authority"] == personal["authority"] == "NONE"
    assert personal["classification"] == "OWNER_DECLARED_PREFERENCE"
    assert client.get(PATH, params={"person_id": personal["person_id"]}).json()["items"] == [
        personal
    ]
    assert client.get(PATH, params={"scope": "household"}).json()["items"] == [shared]
    fresh_memory = MemoryService(url, index_enabled=False) if url else memory
    fresh_graph = PostgresHouseholdGraph(url) if url else graph
    refreshed, refreshed_headers = login(preferences_service(fresh_memory, fresh_graph, fixture)[0])
    assert refreshed.get(PATH).json()["items"] == items
    response = mutate(
        refreshed,
        refreshed_headers,
        "update",
        {
            "preference_id": personal["preference_id"],
            "content": "Synthetic corrected personal wording",
        },
    )
    assert response.json()["status"] == "SUCCEEDED"
    changed = refreshed.get(PATH, params={"person_id": personal["person_id"]}).json()["items"][0]
    assert changed["version"] != personal["version"]
    assert changed["supersedes_preference_id"] == personal["preference_id"]
    assert changed["scope"] == "personal" and changed["category"] == "notifications"
    rejected(
        mutate(
            refreshed,
            refreshed_headers,
            "update",
            {
                "preference_id": personal["preference_id"],
                "content": "Stale synthetic edit",
            },
        )
    )
    rejected(
        mutate(
            refreshed, refreshed_headers, "retract", {"preference_id": personal["preference_id"]}
        )
    )
    assert (
        mutate(
            refreshed, refreshed_headers, "retract", {"preference_id": changed["preference_id"]}
        ).json()["status"]
        == "SUCCEEDED"
    )
    assert refreshed.get(PATH).json()["items"] == [shared]
    original = memory.get(UUID(personal["preference_id"]))
    latest = memory.get(UUID(changed["preference_id"]))
    assert original.status == MemoryStatus.SUPERSEDED and original.content == personal["content"]
    assert latest.status == MemoryStatus.RETRACTED and latest.content == changed["content"]
    assert evaluator.documents and evaluator.documents[0]["origin"] == "DIRECT_USER"


def test_production_api_auth_csrf_forged_authority_and_policy_denial_precede_writes() -> None:
    memory, graph, fixture, _ = prepared()
    service, evaluator = preferences_service(memory, graph, fixture)
    assert TestClient(create_app(service)).get(PATH).status_code == 401
    client, headers = login(service)
    assert mutate(client, {}, "create", {"content": "Synthetic"}).status_code == 403
    assert (
        mutate(
            client,
            {**headers, "Origin": "https://foreign.invalid"},
            "create",
            {"content": "Synthetic"},
        ).status_code
        == 403
    )
    for field in (
        "authority",
        "policy",
        "semantic_role",
        "household_id",
        "source_ref",
        "principal_id",
        "action",
    ):
        rejected(mutate(client, headers, "create", {"content": "Synthetic", field: "owner"}))
    assert not memory.records and not evaluator.documents
    evaluator.decision = "DENY"
    assert mutate(client, headers, "create", {"content": "Synthetic"}).json()["status"] == "DENIED"
    assert not memory.records


def test_foreign_person_and_preference_ids_never_cross_household_boundary() -> None:
    memory, graph, fixture, _ = prepared()
    client, headers = login(preferences_service(memory, graph, fixture)[0])
    assert (
        mutate(client, headers, "create", {"content": "Synthetic"}).json()["status"] == "SUCCEEDED"
    )
    original = client.get(PATH).json()["items"][0]
    key = UUID(original["preference_id"])
    memory.records[key] = replace(memory.records[key], household_id=uuid4())
    assert client.get(PATH).json()["items"] == []
    for operation in ("update", "retract"):
        payload = {"preference_id": str(key)}
        if operation == "update":
            payload["content"] = "Synthetic foreign edit"
        rejected(mutate(client, headers, operation, payload))
    rejected(
        mutate(
            client,
            headers,
            "create",
            {"content": "Synthetic", "person_id": str(fixture.foreign.canonical_id)},
        )
    )
    assert (
        client.get(PATH, params={"person_id": str(fixture.foreign.canonical_id)}).status_code == 400
    )
    assert len(memory.records) == 1 and memory.records[key].status == MemoryStatus.ACTIVE


def test_resident_options_are_read_only_and_owner_guard_survives_fixture_policy_allow() -> None:
    memory, graph, fixture, _ = prepared()
    graph.nodes[fixture.owner.canonical_id] = replace(fixture.owner, metadata={})
    client, headers = login(preferences_service(memory, graph, fixture)[0])
    assert client.get(PATH).json()["can_edit"] is False
    rejected(mutate(client, headers, "create", {"content": "Synthetic"}))
    assert not memory.records


def test_http_cursor_and_category_filters_do_not_silently_omit_records() -> None:
    memory, graph, fixture, _ = prepared()
    client, headers = login(preferences_service(memory, graph, fixture)[0])
    for index in range(4):
        assert (
            mutate(
                client,
                headers,
                "create",
                {
                    "content": f"Synthetic {index}",
                    "category": "general" if index == 0 else "routines",
                },
            ).json()["status"]
            == "SUCCEEDED"
        )
    first = client.get(PATH, params={"limit": 2, "category": "routines"}).json()
    second = client.get(
        PATH, params={"limit": 2, "category": "routines", "cursor": first["next_cursor"]}
    ).json()
    assert len(first["items"]) == 2 and len(second["items"]) == 1
    assert len({item["version"] for item in first["items"] + second["items"]}) == 3
    assert second["next_cursor"] is None
    assert client.get(PATH, params={"limit": 101}).status_code == 400
    assert client.get(PATH, params={"cursor": "not-a-uuid"}).status_code == 400


def test_preference_reads_and_writes_execute_off_asgi_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    from anima_ha import ui_api

    memory, graph, fixture, _ = prepared()
    service, _ = preferences_service(memory, graph, fixture)
    app = create_app(service)
    loop_threads: list[int] = []
    worker_threads: list[int] = []
    original_read, original_write = preferences_page, memory.create

    @app.middleware("http")
    async def record_loop(request: Request, call_next: Any) -> Any:
        loop_threads.append(threading.get_ident())
        return await call_next(request)

    def read(*args: Any, **kwargs: Any) -> Any:
        worker_threads.append(threading.get_ident())
        return original_read(*args, **kwargs)

    def write(*args: Any, **kwargs: Any) -> Any:
        worker_threads.append(threading.get_ident())
        return original_write(*args, **kwargs)

    monkeypatch.setattr(ui_api, "preferences_page", read)
    monkeypatch.setattr(memory, "create", write)
    with TestClient(app, follow_redirects=False) as client:
        response = client.get("/auth/login")
        callback = client.get(response.headers["location"])
        headers = {"Origin": "http://testserver", "X-Anima-CSRF": callback.headers["x-anima-csrf"]}
        assert client.get(PATH).status_code == 200
        assert (
            mutate(client, headers, "create", {"content": "Synthetic"}).json()["status"]
            == "SUCCEEDED"
        )
    assert len(worker_threads) == 2 and not set(worker_threads).intersection(loop_threads)


def test_optin_actual_opa_denial_has_durable_policy_record_and_zero_preferences() -> None:
    opa = os.environ.get("ANIMA_FAMILY_ROUTINES_TEST_OPA_URL")
    if not opa:
        pytest.skip("requires isolated ANIMA_FAMILY_ROUTINES_TEST_OPA_URL")
    memory, graph, fixture, url = prepared(True)
    assert url is not None
    service, _ = preferences_service(memory, graph, fixture)
    commands = cast(CoreUICommandGateway, service.commands)
    commands.policy_service = PolicyService(
        OpaPolicyClient(opa), audit_store=PostgresPolicyStore(url)
    )
    commands.policy_role_resolver = lambda _: "guest"
    client, headers = login(service)
    response = mutate(
        client,
        headers,
        "create",
        {"content": "Synthetic denied preference", "person_id": str(fixture.person.canonical_id)},
    )
    assert response.status_code == 200 and response.json()["status"] == "DENIED"
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
