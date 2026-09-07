"""Isolated browser fixture: real routine Core/Memory, synthetic household only."""

from __future__ import annotations

import os
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
from anima_ha.memory import MemoryService
from anima_ha.policy import OpaPolicyClient, PolicyService, PostgresPolicyStore
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
    service, _ = service_for(MemoryService(url), graph, fixture)
    cast(CoreUICommandGateway, service.commands).policy_service = PolicyService(
        OpaPolicyClient(os.environ["ANIMA_FAMILY_ROUTINES_TEST_OPA_URL"]),
        audit_store=PostgresPolicyStore(url),
    )
    # No owner runtime/HA client is constructed. Real OPA uses unchanged policy;
    # browser identity and household records are isolated test fixtures.
    uvicorn.run(create_app(service), host="127.0.0.1", port=18291, log_level="warning")


if __name__ == "__main__":
    main()
