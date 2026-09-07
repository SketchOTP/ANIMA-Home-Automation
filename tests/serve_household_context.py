"""Disposable real-PG/OPA owner context fixture, never production startup."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import psycopg
import uvicorn
from test_family_routines import Graph
from test_family_routines_api import service_for

from anima_ha.db.migrate import migrate
from anima_ha.graph import (
    CanonicalRelationship,
    CommissioningDocument,
    PostgresHouseholdGraph,
    RelationshipType,
)
from anima_ha.household_event_context import HouseholdEventEvidence
from anima_ha.household_learning import (
    HOUSEHOLD_LEARNING_MANIFEST,
    HouseholdLearningNativePlugin,
    HouseholdLearningService,
)
from anima_ha.journal import PostgresEventJournal
from anima_ha.knowledge import KNOWLEDGE_MANIFEST, KnowledgeConfig, KnowledgeNativePlugin
from anima_ha.memory import MemoryService
from anima_ha.plugins import NativeRuntime
from anima_ha.policy import OpaPolicyClient, PolicyService, PostgresPolicyStore
from anima_ha.preferences import PREFERENCES_MANIFEST, PreferencesNativePlugin
from anima_ha.tasks import PostgresTaskStore, TaskService
from anima_ha.ui_api import create_app
from anima_ha.ui_runtime import CoreUICommandGateway


def main() -> None:
    url = os.environ["ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL"]
    with psycopg.connect(url) as connection:
        if connection.execute("SELECT current_database()").fetchone() != (
            "anima_family_routines_test",
        ):
            raise RuntimeError("Dedicated synthetic test database required")
    migrate(url, 5)
    fixture = Graph()
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
    service, _ = service_for(memory, graph, fixture)
    gateway = cast(CoreUICommandGateway, service.commands)
    gateway.policy_service = PolicyService(
        OpaPolicyClient(os.environ["ANIMA_FAMILY_ROUTINES_TEST_OPA_URL"]),
        audit_store=PostgresPolicyStore(url),
    )
    gateway.manager.register(
        PREFERENCES_MANIFEST, NativeRuntime(PreferencesNativePlugin(memory, graph))
    )
    gateway.manager.enable(PREFERENCES_MANIFEST.plugin_id)
    journal = PostgresEventJournal(url)
    learning = HouseholdLearningService(
        memory,
        graph,
        journal,
        evidence_reader=HouseholdEventEvidence(url, graph).recent_household_evidence,
        task_service=TaskService(PostgresTaskStore(url), journal),
    )
    gateway.manager.register(
        HOUSEHOLD_LEARNING_MANIFEST, NativeRuntime(HouseholdLearningNativePlugin(learning))
    )
    gateway.manager.enable(HOUSEHOLD_LEARNING_MANIFEST.plugin_id)
    service.core_runtime = SimpleNamespace(
        learning_service=learning, home_assistant_adapter=None, graph=graph
    )
    with tempfile.TemporaryDirectory(prefix="anima-context-test-vault-") as directory:
        gateway.manager.register(
            KNOWLEDGE_MANIFEST,
            NativeRuntime(
                KnowledgeNativePlugin(
                    KnowledgeConfig(Path(directory)),
                    person_validator=lambda household, person: any(
                        item.canonical_id == person
                        for item in graph.members_of_household(household)
                    ),
                )
            ),
        )
        gateway.manager.enable(KNOWLEDGE_MANIFEST.plugin_id)
        uvicorn.run(create_app(service), host="127.0.0.1", port=18293, log_level="warning")


if __name__ == "__main__":
    main()
