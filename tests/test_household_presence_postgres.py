"""Actual PostgreSQL/OPA/HTTP presence wiring with synthetic classified trackers.

Classifier provenance and HA hardware are fixtures, not physical qualification.
Only the dedicated routines test database may be used; no owner data or scans.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from test_family_routines_api import login

from anima_ha.db.migrate import migrate
from anima_ha.events import EventEnvelope, EvidenceKind, TruthObservation
from anima_ha.graph import (
    CanonicalNode,
    CanonicalRelationship,
    CommissioningDocument,
    NodeKind,
    PostgresHouseholdGraph,
    ProviderReference,
    RelationshipType,
    TargetKind,
)
from anima_ha.household_presence import (
    HOUSEHOLD_PRESENCE_MANIFEST,
    HouseholdPresenceNativePlugin,
    HouseholdPresenceService,
    SignalKind,
)
from anima_ha.journal import PostgresRealityStore, PostgresTruthProjection
from anima_ha.plugins import NativeRuntime, PluginManager
from anima_ha.policy import OpaPolicyClient, PolicyService, PostgresPolicyStore
from anima_ha.ui_api import UIConfig, UIService
from anima_ha.ui_runtime import CoreUICommandGateway

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)
PATH = "/api/v1/presence"


@pytest.fixture
def database_url() -> str:
    url = os.environ.get("ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL")
    if not url or not os.environ.get("ANIMA_FAMILY_ROUTINES_TEST_OPA_URL"):
        pytest.skip("requires isolated routines PostgreSQL and real OPA")
    with psycopg.connect(url) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "anima_family_routines_test",
        )
    migrate(url, 5)
    return url


@dataclass
class Household:
    graph: PostgresHouseholdGraph
    home: CanonicalNode
    owner: CanonicalNode
    member: CanonicalNode
    phone: CanonicalNode
    cap: CanonicalNode
    instance: UUID
    reference: ProviderReference

    @property
    def truth_key(self) -> str:
        return f"state/capability/{self.cap.canonical_id}/value"


def commission(database_url: str) -> Household:
    graph = PostgresHouseholdGraph(database_url)
    home = CanonicalNode(uuid4(), NodeKind.HOUSEHOLD, "Synthetic presence home")
    owner = CanonicalNode(
        uuid4(), NodeKind.PERSON, "Synthetic owner", metadata={"semantic_role": "owner"}
    )
    member = CanonicalNode(
        uuid4(), NodeKind.PERSON, "Synthetic member", metadata={"semantic_role": "guest"}
    )
    phone = CanonicalNode(uuid4(), NodeKind.SENSOR, "Synthetic phone")
    cap = CanonicalNode(uuid4(), NodeKind.CAPABILITY, "Synthetic router presence")
    instance = uuid4()
    reference = ProviderReference(
        uuid4(),
        "home_assistant",
        str(instance),
        "entity",
        f"device_tracker.synthetic_{cap.canonical_id.hex}",
        cap.canonical_id,
        TargetKind.CAPABILITY,
        {"preserved": "SYNTHETIC_PRIVATE_PROVIDER_METADATA"},
    )
    graph.commission(
        CommissioningDocument(
            1,
            (home, owner, member, phone, cap),
            tuple(
                CanonicalRelationship(uuid4(), kind, source.canonical_id, target.canonical_id)
                for kind, source, target in (
                    (RelationshipType.MEMBER_OF, owner, home),
                    (RelationshipType.MEMBER_OF, member, home),
                    (RelationshipType.INSTALLED_IN, phone, home),
                    (RelationshipType.EXPOSES, phone, cap),
                )
            ),
            provider_references=(reference,),
        )
    )
    return Household(graph, home, owner, member, phone, cap, instance, reference)


def client_for(
    database_url: str, household: Household, *, guest: bool = False, now: datetime = NOW
) -> tuple[Any, dict[str, str]]:
    graph = PostgresHouseholdGraph(database_url)
    manager = PluginManager()
    # Trusted test classifier is exact to the commissioned reference, not a raw
    # provider-name heuristic or a caller-supplied qualification flag.
    presence = HouseholdPresenceService(
        graph,
        PostgresTruthProjection(database_url),
        classify_source=lambda ref: (
            SignalKind.ROUTER_WIFI
            if ref.provider_reference_id == household.reference.provider_reference_id
            else None
        ),
    )
    manager.register(
        HOUSEHOLD_PRESENCE_MANIFEST,
        NativeRuntime(
            HouseholdPresenceNativePlugin(presence, household.instance, now=lambda: now),
        ),
    )
    manager.enable(HOUSEHOLD_PRESENCE_MANIFEST.plugin_id)

    def role(person_id: UUID) -> str | None:
        person = graph.get_node(person_id)
        return str(person.metadata["semantic_role"]) if person else None

    gateway = CoreUICommandGateway(
        manager,
        PolicyService(
            OpaPolicyClient(os.environ["ANIMA_FAMILY_ROUTINES_TEST_OPA_URL"]),
            audit_store=PostgresPolicyStore(database_url),
        ),
        policy_role_resolver=role,
    )
    service = UIService(
        config=UIConfig(test_auth_enabled=True),
        commands=gateway,
        read_model=SimpleNamespace(graph=graph),
        ha_user_map={
            "test-ha-user": (
                household.home.canonical_id,
                household.member.canonical_id if guest else household.owner.canonical_id,
            )
        },
    )
    return login(service)


def observe(database_url: str, household: Household, value: str, *, age: int = 5) -> None:
    observation = TruthObservation(
        truth_key=household.truth_key,
        source=f"provider:home_assistant:{household.instance}:{household.reference.external_id}",
        observed_at=NOW - timedelta(seconds=age),
        received_at=NOW - timedelta(seconds=1),
        value=value,
        evidence_kind=EvidenceKind.DIRECT,
        freshness_seconds=600,
        metadata={"coordinates": "SYNTHETIC_COORDINATES", "mac": "SYNTHETIC_MAC"},
    )
    event = EventEnvelope.create(
        event_id=str(uuid4()),
        event_type="truth.observation",
        source=observation.source,
        subject_key=household.truth_key,
        occurred_at=observation.observed_at,
        recorded_at=observation.received_at,
        payload=observation.to_payload(),
    )
    result, projection = PostgresRealityStore(database_url).ingest(event)
    assert result.deduplicated is False and projection is not None


def source_handle(client: Any) -> str:
    response = client.get(PATH + "/sources")
    assert response.status_code == 200, response.text
    assert response.json()["source_status"] == "QUALIFIED_SOURCES"
    assert len(response.json()["items"]) == 1
    return str(response.json()["items"][0]["source_handle"])


def bind(client: Any, headers: dict[str, str], person: UUID, handle: str) -> Any:
    return client.post(
        PATH + "/bind",
        headers=headers,
        json={
            "payload": {
                "person_id": str(person),
                "source_handle": handle,
                "freshness_seconds": 300,
            }
        },
    )


def test_real_opa_owner_binding_persists_and_http_reload_projects_coarse_truth(
    database_url: str,
) -> None:
    household = commission(database_url)
    client, headers = client_for(database_url, household)
    handle = source_handle(client)
    assert client.get(PATH).json()["can_edit"] is True
    response = bind(client, headers, household.member.canonical_id, handle)
    assert response.status_code == 200 and response.json()["status"] == "SUCCEEDED", response.text
    assert (
        bind(client, headers, household.member.canonical_id, handle).json()["status"] == "SUCCEEDED"
    )
    graph = PostgresHouseholdGraph(database_url)
    refs = graph.provider_references_for(household.cap.canonical_id)
    assert len(refs) == 2
    assert next(ref for ref in refs if ref.provider == "home_assistant") == household.reference
    assert graph.related(household.member.canonical_id, RelationshipType.ASSOCIATED_WITH) == [
        household.phone
    ]
    observe(database_url, household, "home")
    fresh, _ = client_for(database_url, household)
    assert source_handle(fresh) == handle
    response = fresh.get(PATH, params={"person_id": str(household.member.canonical_id)})
    assert response.status_code == 200, response.text
    page = response.json()
    item = page["items"][0]
    assert item["binding_status"] == "CONFIGURED" and item["value"] == "HOME"
    assert (
        item["status"] == "CURRENT/KNOWN" and item["evidence_basis"] == "ASSOCIATED_DEVICE_REPORTS"
    )
    assert item["is_authentication"] is False and item["door_actor_verified"] is False
    assert item["signals"][0]["physical_observed_at"] is None
    assert page["external_content_trust"] == "EXTERNAL_UNTRUSTED"
    safe = response.text + fresh.get(PATH + "/sources").text
    for private in (
        household.reference.external_id,
        "SYNTHETIC_COORDINATES",
        "SYNTHETIC_MAC",
        "SYNTHETIC_PRIVATE_PROVIDER_METADATA",
    ):
        assert private not in safe
    stale, _ = client_for(database_url, household, now=NOW + timedelta(seconds=301))
    assert (
        stale.get(PATH, params={"person_id": str(household.member.canonical_id)}).json()["items"][
            0
        ]["status"]
        == "STALE"
    )
    observe(database_url, household, "not_home", age=1)
    absent = fresh.get(PATH, params={"person_id": str(household.member.canonical_id)}).json()[
        "items"
    ][0]
    assert absent["signals"][0]["value"] == "NOT_DETECTED"
    assert absent["value"] == "UNKNOWN"  # Router absence does not prove person away.
    with psycopg.connect(database_url) as connection:
        rows = connection.execute(
            "SELECT decision, reason_code, input_snapshot FROM anima_policy_decisions "
            "WHERE household_id=%s",
            (household.home.canonical_id,),
        ).fetchall()
        writes = [
            row for row in rows if row[2]["action_intent"]["risk_class"] == "SECURITY_SECURE_ACTION"
        ]
        assert len(writes) == 2 and all(
            row[:2] == ("ALLOW", "SECURE_ACTION_AUTHORIZED") for row in writes
        )
        assert all(row[2]["origin"] == "DIRECT_USER" for row in writes)
        assert connection.execute(
            "SELECT count(*) FROM anima_truth_observations WHERE truth_key=%s",
            (household.truth_key,),
        ).fetchone() == (2,)


def test_real_opa_guest_denial_has_zero_presence_mapping_changes(database_url: str) -> None:
    household = commission(database_url)
    client, headers = client_for(database_url, household, guest=True)
    assert client.get(PATH).json()["can_edit"] is False
    response = bind(client, headers, household.member.canonical_id, source_handle(client))
    assert response.status_code == 200 and response.json()["status"] == "DENIED"
    graph = PostgresHouseholdGraph(database_url)
    assert graph.provider_references_for(household.cap.canonical_id) == [household.reference]
    assert graph.related(household.member.canonical_id, RelationshipType.ASSOCIATED_WITH) == []
    with psycopg.connect(database_url) as connection:
        assert connection.execute(
            "SELECT count(*) FROM anima_policy_decisions WHERE household_id=%s "
            "AND decision='DENY' AND reason_code='POLICY_DEFAULT_DENY'",
            (household.home.canonical_id,),
        ).fetchone() == (1,)


def test_cross_household_source_and_member_rejected_without_graph_or_truth_changes(
    database_url: str,
) -> None:
    household, foreign = commission(database_url), commission(database_url)
    client, headers = client_for(database_url, household)
    other_client, _ = client_for(database_url, foreign)
    own_handle, foreign_handle = source_handle(client), source_handle(other_client)
    for person, handle in (
        (foreign.member.canonical_id, own_handle),
        (household.member.canonical_id, foreign_handle),
    ):
        response = bind(client, headers, person, handle)
        assert response.status_code == 200 and response.json()["status"] != "SUCCEEDED"
    assert (
        client.get(PATH, params={"person_id": str(foreign.member.canonical_id)}).status_code != 200
    )
    assert str(foreign.cap.canonical_id) not in json.dumps(client.get(PATH + "/sources").json())
    graph = PostgresHouseholdGraph(database_url)
    for fixture in (household, foreign):
        assert graph.provider_references_for(fixture.cap.canonical_id) == [fixture.reference]
        assert graph.related(fixture.member.canonical_id, RelationshipType.ASSOCIATED_WITH) == []
        with psycopg.connect(database_url) as connection:
            assert connection.execute(
                "SELECT count(*) FROM anima_truth_observations WHERE truth_key=%s",
                (fixture.truth_key,),
            ).fetchone() == (0,)
