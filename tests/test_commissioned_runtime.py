from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest

from anima_ha.graph import CanonicalNode, NodeKind
from anima_ha.ui_api import (
    DEFAULT_UI_PREFERENCES,
    DemoHouseholdReadModel,
    PostgresHouseholdReadModel,
    PrincipalMappingConflict,
    PrincipalMappingRequired,
    UIConfig,
    UIIdentity,
    UIService,
)
from anima_ha.ui_runtime import PostgresCommissionedIdentityResolver

HOUSEHOLD = UUID("00000000-0000-0000-0000-000000000012")
PERSON = UUID("00000000-0000-0000-0000-000000000013")
RESOURCE = UUID("00000000-0000-0000-0000-000000000014")


def node(identifier: UUID, kind: NodeKind, name: str, **metadata: object) -> CanonicalNode:
    return CanonicalNode(identifier, kind, name, metadata=dict(metadata))


class GraphStub:
    def __init__(self, targets: list[CanonicalNode], households: list[CanonicalNode]) -> None:
        self.targets = targets
        self.households = households

    def resolve_provider_references(self, *args: str) -> list[CanonicalNode]:
        del args
        return self.targets

    def households_for_member(self, member_id: UUID) -> list[CanonicalNode]:
        del member_id
        return self.households

    def get_node(self, identifier: UUID) -> CanonicalNode | None:
        return next(
            (item for item in [*self.targets, *self.households] if item.canonical_id == identifier),
            None,
        )

    def provider_references_for(self, identifier: UUID) -> list[SimpleNamespace]:
        del identifier
        return []


def test_commissioned_identity_requires_exact_person_and_household() -> None:
    resolver = PostgresCommissionedIdentityResolver(
        GraphStub(
            [node(PERSON, NodeKind.PERSON, "Alex")], [node(HOUSEHOLD, NodeKind.HOUSEHOLD, "Home")]
        ),
        "instance-1",
    )
    assert resolver.resolve_ha_user("ha-user") == (HOUSEHOLD, PERSON)

    missing = PostgresCommissionedIdentityResolver(GraphStub([], []), "instance-1")
    with pytest.raises(PrincipalMappingRequired, match="PRINCIPAL_MAPPING_REQUIRED"):
        missing.resolve_ha_user("unmapped")

    conflict = PostgresCommissionedIdentityResolver(
        GraphStub(
            [node(PERSON, NodeKind.PERSON, "Alex"), node(RESOURCE, NodeKind.RESOURCE, "Other")],
            [node(HOUSEHOLD, NodeKind.HOUSEHOLD, "Home")],
        ),
        "instance-1",
    )
    with pytest.raises(PrincipalMappingConflict, match="PRINCIPAL_MAPPING_CONFLICT"):
        conflict.resolve_ha_user("ambiguous")


def test_normal_ui_service_does_not_create_synthetic_identity() -> None:
    service = UIService(config=UIConfig(test_auth_enabled=False))
    with pytest.raises(PrincipalMappingRequired, match="PRINCIPAL_MAPPING_REQUIRED"):
        service.map_ha_user("test-ha-user")


def test_postgres_read_model_uses_graph_and_registry_not_demo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    household = node(HOUSEHOLD, NodeKind.HOUSEHOLD, "Commissioned Home")
    person = node(PERSON, NodeKind.PERSON, "Alex")
    resource = node(RESOURCE, NodeKind.RESOURCE, "Desk Lamp")
    capability = node(
        UUID("00000000-0000-0000-0000-000000000015"),
        NodeKind.CAPABILITY,
        "Power",
        capability_type="power.switch",
    )

    class Graph:
        def get_node(self, identifier: UUID) -> CanonicalNode | None:
            return {HOUSEHOLD: household, PERSON: person, RESOURCE: resource}.get(identifier)

        def members_of_household(self, identifier: UUID) -> list[CanonicalNode]:
            assert identifier == HOUSEHOLD
            return [person]

        def truth_for_node(self, identifier: UUID, truth: object) -> list[tuple[object, object]]:
            del identifier, truth
            return []

        def resources_in_place(self, identifier: UUID) -> list[CanonicalNode]:
            assert identifier == HOUSEHOLD
            return [resource]

        def resource_capabilities(self, identifier: UUID) -> list[CanonicalNode]:
            assert identifier == RESOURCE
            return [capability]

    plugins = SimpleNamespace(
        list_plugins=lambda: [
            SimpleNamespace(
                enabled=True,
                last_error=None,
                manifest=SimpleNamespace(capabilities=("shopping-research",), name="UPCitemdb"),
            )
        ]
    )
    model = PostgresHouseholdReadModel(
        "postgresql://unused", graph=Graph(), truth=object(), plugins=plugins
    )
    monkeypatch.setattr(
        DemoHouseholdReadModel, "bootstrap", lambda *args: pytest.fail("demo bootstrap used")
    )
    monkeypatch.setattr(DemoHouseholdReadModel, "home", lambda *args: pytest.fail("demo home used"))
    monkeypatch.setattr(
        DemoHouseholdReadModel, "capabilities", lambda *args: pytest.fail("demo capabilities used")
    )
    monkeypatch.setattr(model, "tasks", lambda identity: [])
    monkeypatch.setattr(model, "calendar", lambda identity: [])
    monkeypatch.setattr(model, "activity", lambda identity: [])
    monkeypatch.setattr(model, "settings", lambda identity: dict(DEFAULT_UI_PREFERENCES))
    monkeypatch.setattr(model, "weather", lambda identity: {"status": "UNKNOWN"})
    identity = UIIdentity(HOUSEHOLD, PERSON, "ha-user", SimpleNamespace())  # type: ignore[arg-type]

    assert model.bootstrap(identity)["household"] == {
        "name": "Commissioned Home",
        "mode": "commissioned",
    }
    home = model.home(identity)
    assert home["presence"]["people"] == [{"name": "Alex", "state": "unknown"}]
    assert home["controls"][0]["control_id"] == str(RESOURCE)
    assert model.capabilities(identity)[1]["id"] == "shopping-research"
