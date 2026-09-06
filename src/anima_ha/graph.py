"""ANIMA-owned canonical household graph contracts and PostgreSQL repository.

The graph is commissioned topology, not a provider registry mirror and not a
permission system.  All identifiers are UUIDs owned by ANIMA; provider IDs are
kept in a separate reference table.
"""

# SQL statements are kept readable as multiline queries; Ruff's line-length
# rule is retained for the rest of the repository.
# ruff: noqa: E501

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.journal import PostgresEventJournal
from anima_ha.truth import TruthResolution, TruthStatus


class GraphValidationError(ValueError):
    """Raised when a commissioning document or graph mutation is invalid."""


class GraphConflict(GraphValidationError):
    """Raised when an identity or provider reference would become ambiguous."""


class NodeKind(StrEnum):
    HOUSEHOLD = "HOUSEHOLD"
    PROPERTY = "PROPERTY"
    BUILDING = "BUILDING"
    FLOOR = "FLOOR"
    ROOM = "ROOM"
    ZONE = "ZONE"
    OUTSIDE = "OUTSIDE"
    ENTRANCE = "ENTRANCE"
    RESOURCE = "RESOURCE"
    SENSOR = "SENSOR"
    PERSON = "PERSON"
    PET = "PET"
    VEHICLE = "VEHICLE"
    CAPABILITY = "CAPABILITY"


class RelationshipType(StrEnum):
    CONTAINS = "CONTAINS"
    MEMBER_OF = "MEMBER_OF"
    CONNECTS = "CONNECTS"
    INSTALLED_IN = "INSTALLED_IN"
    EXPOSES = "EXPOSES"
    MONITORS = "MONITORS"
    CONTROLS = "CONTROLS"
    COVERS = "COVERS"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"


class TargetKind(StrEnum):
    NODE = "NODE"
    CAPABILITY = "CAPABILITY"


@dataclass(frozen=True, slots=True)
class CanonicalNode:
    canonical_id: UUID
    kind: NodeKind
    name: str
    security_sensitive: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    retired_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CanonicalRelationship:
    relationship_id: UUID
    relationship_type: RelationshipType
    source_id: UUID
    target_id: UUID
    metadata: dict[str, Any] = field(default_factory=dict)
    retired_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Alias:
    alias_id: UUID
    display_alias: str
    canonical_id: UUID
    node_kind: NodeKind
    scope_id: UUID | None = None
    retired_at: datetime | None = None

    @property
    def normalized_alias(self) -> str:
        return normalize_alias(self.display_alias)


@dataclass(frozen=True, slots=True)
class ProviderReference:
    provider_reference_id: UUID
    provider: str
    provider_scope: str
    external_object_kind: str
    external_id: str
    target_id: UUID
    target_kind: TargetKind = TargetKind.NODE
    metadata: dict[str, Any] = field(default_factory=dict)
    retired_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class TruthBinding:
    binding_id: UUID
    target_id: UUID
    target_kind: TargetKind
    truth_key: str
    semantic_attribute: str
    metadata: dict[str, Any] = field(default_factory=dict)
    retired_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CommissioningDocument:
    version: int
    nodes: tuple[CanonicalNode, ...]
    relationships: tuple[CanonicalRelationship, ...] = ()
    aliases: tuple[Alias, ...] = ()
    provider_references: tuple[ProviderReference, ...] = ()
    truth_bindings: tuple[TruthBinding, ...] = ()

    @classmethod
    def from_dict(cls, document: dict[str, Any]) -> CommissioningDocument:
        if int(document.get("version", 0)) != 1:
            raise GraphValidationError("commissioning version must be 1")

        def identifier(value: Any) -> UUID:
            try:
                return UUID(str(value))
            except (TypeError, ValueError) as exc:
                raise GraphValidationError(f"invalid canonical UUID: {value!r}") from exc

        nodes = tuple(
            CanonicalNode(
                canonical_id=identifier(item["canonical_id"]),
                kind=NodeKind(str(item["kind"])),
                name=str(item["name"]),
                security_sensitive=bool(item.get("security_sensitive", False)),
                metadata=dict(item.get("metadata", {})),
            )
            for item in document.get("nodes", [])
        )
        relationships = tuple(
            CanonicalRelationship(
                relationship_id=identifier(item["relationship_id"]),
                relationship_type=RelationshipType(str(item["relationship_type"])),
                source_id=identifier(item["source_id"]),
                target_id=identifier(item["target_id"]),
                metadata=dict(item.get("metadata", {})),
            )
            for item in document.get("relationships", [])
        )
        aliases = tuple(
            Alias(
                alias_id=identifier(item["alias_id"]),
                display_alias=str(item["display_alias"]),
                canonical_id=identifier(item["canonical_id"]),
                node_kind=NodeKind(str(item["node_kind"])),
                scope_id=identifier(item["scope_id"]) if item.get("scope_id") else None,
            )
            for item in document.get("aliases", [])
        )
        provider_references = tuple(
            ProviderReference(
                provider_reference_id=identifier(item["provider_reference_id"]),
                provider=str(item["provider"]),
                provider_scope=str(item["provider_scope"]),
                external_object_kind=str(item["external_object_kind"]),
                external_id=str(item["external_id"]),
                target_id=identifier(item["target_id"]),
                target_kind=TargetKind(str(item.get("target_kind", "NODE"))),
                metadata=dict(item.get("metadata", {})),
            )
            for item in document.get("provider_references", [])
        )
        truth_bindings = tuple(
            TruthBinding(
                binding_id=identifier(item["binding_id"]),
                target_id=identifier(item["target_id"]),
                target_kind=TargetKind(str(item.get("target_kind", "NODE"))),
                truth_key=str(item["truth_key"]),
                semantic_attribute=str(item["semantic_attribute"]),
                metadata=dict(item.get("metadata", {})),
            )
            for item in document.get("truth_bindings", [])
        )
        result = cls(1, nodes, relationships, aliases, provider_references, truth_bindings)
        validate_commissioning(result)
        return result


@dataclass(frozen=True, slots=True)
class CommissionResult:
    created_nodes: int
    created_relationships: int
    created_aliases: int
    created_provider_references: int
    created_truth_bindings: int
    audit_events: int


@dataclass(frozen=True, slots=True)
class AliasResolution:
    query: str
    status: str
    candidates: tuple[CanonicalNode, ...] = ()


class TruthReader(Protocol):
    def get(self, truth_key: str, *, now: datetime | None = None) -> TruthResolution: ...


PLACE_KINDS = {
    NodeKind.HOUSEHOLD,
    NodeKind.PROPERTY,
    NodeKind.BUILDING,
    NodeKind.FLOOR,
    NodeKind.ROOM,
    NodeKind.ZONE,
    NodeKind.OUTSIDE,
}
CONTAINER_KINDS = PLACE_KINDS


def normalize_alias(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def validate_commissioning(document: CommissioningDocument) -> None:
    if document.version != 1:
        raise GraphValidationError("unsupported commissioning version")
    nodes = {node.canonical_id: node for node in document.nodes}
    if len(nodes) != len(document.nodes):
        raise GraphConflict("duplicate canonical node identity")
    if not nodes:
        raise GraphValidationError("commissioning document must contain nodes")
    if sum(node.kind == NodeKind.HOUSEHOLD for node in document.nodes) != 1:
        raise GraphValidationError("commissioning document must contain exactly one household")
    relationship_ids = {item.relationship_id for item in document.relationships}
    if len(relationship_ids) != len(document.relationships):
        raise GraphConflict("duplicate relationship identity")
    aliases_by_key: dict[tuple[str, UUID | None], UUID] = {}
    provider_keys: set[tuple[str, str, str, str]] = set()
    contains: dict[UUID, list[UUID]] = defaultdict(list)
    connects_by_entrance: dict[UUID, list[UUID]] = defaultdict(list)
    for relationship in document.relationships:
        source = nodes.get(relationship.source_id)
        target = nodes.get(relationship.target_id)
        if source is None or target is None:
            raise GraphValidationError("relationship contains a dangling node reference")
        if relationship.source_id == relationship.target_id:
            raise GraphValidationError("self relationships are not valid")
        if relationship.relationship_type == RelationshipType.CONTAINS:
            if source.kind not in CONTAINER_KINDS or target.kind == NodeKind.CAPABILITY:
                raise GraphValidationError("CONTAINS requires a place/container source")
            contains[source.canonical_id].append(target.canonical_id)
        elif relationship.relationship_type == RelationshipType.CONNECTS:
            if source.kind != NodeKind.ENTRANCE or target.kind not in PLACE_KINDS:
                raise GraphValidationError("CONNECTS requires entrance -> place endpoints")
            connects_by_entrance[source.canonical_id].append(target.canonical_id)
        elif relationship.relationship_type == RelationshipType.INSTALLED_IN:
            if (
                source.kind not in {NodeKind.RESOURCE, NodeKind.SENSOR}
                or target.kind not in PLACE_KINDS
            ):
                raise GraphValidationError("INSTALLED_IN requires resource/sensor -> place")
        elif relationship.relationship_type == RelationshipType.EXPOSES:
            if (
                source.kind not in {NodeKind.RESOURCE, NodeKind.SENSOR}
                or target.kind != NodeKind.CAPABILITY
            ):
                raise GraphValidationError("EXPOSES requires resource/sensor -> capability")
        elif relationship.relationship_type == RelationshipType.MEMBER_OF:
            if (
                source.kind not in {NodeKind.PERSON, NodeKind.PET, NodeKind.VEHICLE}
                or target.kind != NodeKind.HOUSEHOLD
            ):
                raise GraphValidationError("MEMBER_OF requires person/pet/vehicle -> household")
        elif relationship.relationship_type == RelationshipType.MONITORS:
            if source.kind != NodeKind.SENSOR:
                raise GraphValidationError("MONITORS requires sensor as source")
        elif relationship.relationship_type == RelationshipType.CONTROLS:
            if source.kind != NodeKind.CAPABILITY:
                raise GraphValidationError("CONTROLS requires capability as source")
        elif relationship.relationship_type == RelationshipType.COVERS:
            if source.kind not in {
                NodeKind.RESOURCE,
                NodeKind.SENSOR,
            } or target.kind not in PLACE_KINDS | {NodeKind.ENTRANCE}:
                raise GraphValidationError("COVERS requires resource/sensor -> place or entrance")
    for _entrance_id, endpoints in connects_by_entrance.items():
        if len(endpoints) != 2 or len(set(endpoints)) != 2:
            raise GraphValidationError("each entrance must connect exactly two distinct places")
    visiting: set[UUID] = set()
    visited: set[UUID] = set()

    def visit(node_id: UUID) -> None:
        if node_id in visiting:
            raise GraphValidationError("place containment cycle detected")
        if node_id in visited:
            return
        visiting.add(node_id)
        for child_id in contains.get(node_id, []):
            visit(child_id)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in nodes:
        visit(node_id)
    for alias in document.aliases:
        node = nodes.get(alias.canonical_id)
        if node is None or node.kind != alias.node_kind:
            raise GraphValidationError("alias target or node kind is invalid")
        if alias.scope_id is not None and alias.scope_id not in nodes:
            raise GraphValidationError("alias scope does not exist")
        normalized = normalize_alias(alias.display_alias)
        if not normalized:
            raise GraphValidationError("alias must not be empty")
        alias_key = (normalized, alias.scope_id)
        prior = aliases_by_key.get(alias_key)
        if prior is not None and prior != alias.canonical_id:
            raise GraphConflict("alias is ambiguous within its scope")
        aliases_by_key[alias_key] = alias.canonical_id
    for reference in document.provider_references:
        target = nodes.get(reference.target_id)
        if target is None:
            raise GraphValidationError("provider reference target does not exist")
        if reference.target_kind == TargetKind.CAPABILITY and target.kind != NodeKind.CAPABILITY:
            raise GraphValidationError("CAPABILITY provider reference must target a capability")
        if reference.target_kind == TargetKind.NODE and target.kind == NodeKind.CAPABILITY:
            raise GraphValidationError("NODE provider reference cannot target a capability")
        provider_key = (
            reference.provider,
            reference.provider_scope,
            reference.external_object_kind,
            reference.external_id,
        )
        if provider_key in provider_keys:
            raise GraphConflict("duplicate provider reference identity")
        provider_keys.add(provider_key)
    for binding in document.truth_bindings:
        target = nodes.get(binding.target_id)
        if target is None:
            raise GraphValidationError("truth binding target does not exist")
        if binding.target_kind == TargetKind.CAPABILITY and target.kind != NodeKind.CAPABILITY:
            raise GraphValidationError("CAPABILITY truth binding must target a capability")
        if binding.target_kind == TargetKind.NODE and target.kind == NodeKind.CAPABILITY:
            raise GraphValidationError("NODE truth binding cannot target a capability")
        if not binding.truth_key.strip() or not binding.semantic_attribute.strip():
            raise GraphValidationError("truth binding key and semantic attribute are required")


class PostgresHouseholdGraph:
    """Durable graph repository and semantic query service."""

    def __init__(self, database_url: str, connect_timeout: int = 5) -> None:
        self.database_url = database_url
        self.connect_timeout = connect_timeout
        self.journal = PostgresEventJournal(database_url, connect_timeout)

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        )

    @staticmethod
    def _node(row: dict[str, Any]) -> CanonicalNode:
        return CanonicalNode(
            canonical_id=UUID(str(row["canonical_id"])),
            kind=NodeKind(str(row["kind"])),
            name=str(row["name"]),
            security_sensitive=bool(row["security_sensitive"]),
            metadata=dict(row["metadata"] or {}),
            retired_at=row["retired_at"],
        )

    @staticmethod
    def _metadata(value: dict[str, Any]) -> str:
        return json.dumps(value, sort_keys=True)

    def _audit(
        self,
        connection: psycopg.Connection[Any],
        operation: str,
        subject: UUID,
        details: dict[str, Any],
    ) -> None:
        event = EventEnvelope.create(
            event_id=str(uuid4()),
            event_type="graph.mutation",
            source="anima.graph",
            subject_key=str(subject),
            occurred_at=datetime.now(UTC),
            payload={"operation": operation, "subject_id": str(subject), **details},
            importance=EventImportance.NORMAL,
            delivery_class=DeliveryClass.GUARANTEED,
            metadata={"audit": True},
        )
        self.journal.append_in_connection(connection, event)

    def commission(self, document: CommissioningDocument) -> CommissionResult:
        validate_commissioning(document)
        counts = [0, 0, 0, 0, 0, 0]
        with self._connect() as connection:
            try:
                with connection.cursor() as cursor:
                    for node in document.nodes:
                        cursor.execute(
                            "SELECT kind, name, security_sensitive, metadata FROM anima_graph_nodes WHERE canonical_id = %s",
                            (node.canonical_id,),
                        )
                        existing = cursor.fetchone()
                        if existing is None:
                            cursor.execute(
                                """INSERT INTO anima_graph_nodes
                                   (canonical_id, kind, name, security_sensitive, metadata)
                                   VALUES (%s, %s, %s, %s, %s::jsonb)""",
                                (
                                    node.canonical_id,
                                    node.kind.value,
                                    node.name,
                                    node.security_sensitive,
                                    self._metadata(node.metadata),
                                ),
                            )
                            counts[0] += 1
                            self._audit(
                                connection,
                                "node.created",
                                node.canonical_id,
                                {"kind": node.kind.value, "name": node.name},
                            )
                        elif str(existing["kind"]) != node.kind.value:
                            raise GraphConflict(
                                f"canonical ID {node.canonical_id} already has another kind"
                            )
                        elif (
                            str(existing["name"]) != node.name
                            or bool(existing["security_sensitive"]) != node.security_sensitive
                            or dict(existing["metadata"] or {}) != node.metadata
                        ):
                            cursor.execute(
                                """UPDATE anima_graph_nodes SET name = %s, security_sensitive = %s,
                                   metadata = %s::jsonb, updated_at = now()
                                   WHERE canonical_id = %s""",
                                (
                                    node.name,
                                    node.security_sensitive,
                                    self._metadata(node.metadata),
                                    node.canonical_id,
                                ),
                            )
                            counts[0] += 1
                            self._audit(
                                connection,
                                "node.updated",
                                node.canonical_id,
                                {"kind": node.kind.value, "name": node.name},
                            )
                    for relationship in document.relationships:
                        cursor.execute(
                            """INSERT INTO anima_graph_relationships
                               (relationship_id, relationship_type, source_id, target_id, metadata)
                               VALUES (%s, %s, %s, %s, %s::jsonb)
                               ON CONFLICT (relationship_type, source_id, target_id)
                               WHERE retired_at IS NULL DO NOTHING
                               RETURNING relationship_id""",
                            (
                                relationship.relationship_id,
                                relationship.relationship_type.value,
                                relationship.source_id,
                                relationship.target_id,
                                self._metadata(relationship.metadata),
                            ),
                        )
                        if cursor.fetchone():
                            counts[1] += 1
                            self._audit(
                                connection,
                                "relationship.added",
                                relationship.relationship_id,
                                {
                                    "relationship_type": relationship.relationship_type.value,
                                    "source_id": str(relationship.source_id),
                                    "target_id": str(relationship.target_id),
                                },
                            )
                    for alias in document.aliases:
                        cursor.execute(
                            """INSERT INTO anima_graph_aliases
                               (alias_id, normalized_alias, display_alias, canonical_id, node_kind, scope_id)
                               VALUES (%s, %s, %s, %s, %s, %s)
                               ON CONFLICT DO NOTHING
                               RETURNING alias_id""",
                            (
                                alias.alias_id,
                                alias.normalized_alias,
                                alias.display_alias,
                                alias.canonical_id,
                                alias.node_kind.value,
                                alias.scope_id,
                            ),
                        )
                        if cursor.fetchone():
                            counts[2] += 1
                            self._audit(
                                connection,
                                "alias.added",
                                alias.alias_id,
                                {
                                    "canonical_id": str(alias.canonical_id),
                                    "alias": alias.display_alias,
                                },
                            )
                    for reference in document.provider_references:
                        cursor.execute(
                            """SELECT provider_reference_id, target_id FROM anima_graph_provider_refs
                               WHERE provider = %s AND provider_scope = %s AND external_object_kind = %s
                                 AND external_id = %s AND retired_at IS NULL""",
                            (
                                reference.provider,
                                reference.provider_scope,
                                reference.external_object_kind,
                                reference.external_id,
                            ),
                        )
                        existing = cursor.fetchone()
                        if existing is not None:
                            if UUID(str(existing["target_id"])) != reference.target_id:
                                raise GraphConflict(
                                    "provider reference collision requires explicit remap"
                                )
                            continue
                        cursor.execute(
                            """INSERT INTO anima_graph_provider_refs
                               (provider_reference_id, provider, provider_scope, external_object_kind,
                                external_id, target_id, target_kind, metadata)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)""",
                            (
                                reference.provider_reference_id,
                                reference.provider,
                                reference.provider_scope,
                                reference.external_object_kind,
                                reference.external_id,
                                reference.target_id,
                                reference.target_kind.value,
                                self._metadata(reference.metadata),
                            ),
                        )
                        counts[3] += 1
                        self._audit(
                            connection,
                            "provider_reference.mapped",
                            reference.provider_reference_id,
                            {
                                "target_id": str(reference.target_id),
                                "provider": reference.provider,
                                "external_id": reference.external_id,
                            },
                        )
                    for binding in document.truth_bindings:
                        cursor.execute(
                            """INSERT INTO anima_graph_truth_bindings
                               (binding_id, target_id, target_kind, truth_key, semantic_attribute, metadata)
                               VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                               ON CONFLICT (target_id, truth_key, semantic_attribute)
                               DO NOTHING RETURNING binding_id""",
                            (
                                binding.binding_id,
                                binding.target_id,
                                binding.target_kind.value,
                                binding.truth_key,
                                binding.semantic_attribute,
                                self._metadata(binding.metadata),
                            ),
                        )
                        if cursor.fetchone():
                            counts[4] += 1
                            self._audit(
                                connection,
                                "truth_binding.added",
                                binding.binding_id,
                                {
                                    "target_id": str(binding.target_id),
                                    "truth_key": binding.truth_key,
                                },
                            )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        counts[5] = sum(counts[:5])
        return CommissionResult(*counts)

    def get_node(self, canonical_id: UUID) -> CanonicalNode | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM anima_graph_nodes WHERE canonical_id = %s", (canonical_id,)
            )
            row = cursor.fetchone()
        return self._node(row) if row else None

    def list_places(self) -> list[CanonicalNode]:
        return self._list_nodes(
            "kind IN ('HOUSEHOLD','PROPERTY','BUILDING','FLOOR','ROOM','ZONE','OUTSIDE')"
        )

    def places_in_household(self, household_id: UUID) -> list[CanonicalNode]:
        """Return active place nodes contained by one commissioned household."""
        return self._list_nodes(
            """canonical_id IN (
                WITH RECURSIVE descendants(canonical_id) AS (
                    SELECT %s::uuid
                    UNION
                    SELECT r.target_id
                    FROM anima_graph_relationships r
                    JOIN descendants d ON d.canonical_id = r.source_id
                    WHERE r.relationship_type = 'CONTAINS' AND r.retired_at IS NULL
                )
                SELECT canonical_id FROM descendants
            ) AND kind IN ('PROPERTY','BUILDING','FLOOR','ROOM','ZONE','OUTSIDE')""",
            (household_id,),
        )

    def _list_nodes(
        self, predicate: str = "TRUE", params: tuple[Any, ...] = ()
    ) -> list[CanonicalNode]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT * FROM anima_graph_nodes WHERE retired_at IS NULL AND {predicate} ORDER BY kind, name, canonical_id",
                params,
            )
            return [self._node(row) for row in cursor.fetchall()]

    def resources_in_place(self, place_id: UUID, recursive: bool = True) -> list[CanonicalNode]:
        if recursive:
            query = """
                WITH RECURSIVE descendants(canonical_id) AS (
                    SELECT %s::uuid
                    UNION
                    SELECT r.target_id FROM anima_graph_relationships r
                    JOIN descendants d ON d.canonical_id = r.source_id
                    WHERE r.relationship_type = 'CONTAINS' AND r.retired_at IS NULL
                )
                SELECT n.* FROM anima_graph_nodes n
                JOIN anima_graph_relationships r ON r.source_id = n.canonical_id
                JOIN descendants d ON d.canonical_id = r.target_id
                WHERE r.relationship_type = 'INSTALLED_IN' AND r.retired_at IS NULL
                  AND n.retired_at IS NULL AND n.kind IN ('RESOURCE','SENSOR')
                ORDER BY n.kind, n.name, n.canonical_id
            """
        else:
            query = """
                SELECT n.* FROM anima_graph_nodes n
                JOIN anima_graph_relationships r ON r.source_id = n.canonical_id
                WHERE r.relationship_type = 'INSTALLED_IN' AND r.target_id = %s
                  AND r.retired_at IS NULL AND n.retired_at IS NULL
                ORDER BY n.kind, n.name, n.canonical_id
            """
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(query, (place_id,))
            return [self._node(row) for row in cursor.fetchall()]

    def entrance_connections(self, entrance_id: UUID) -> list[CanonicalNode]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT n.* FROM anima_graph_nodes n
                   JOIN anima_graph_relationships r ON r.target_id = n.canonical_id
                   WHERE r.source_id = %s AND r.relationship_type = 'CONNECTS'
                     AND r.retired_at IS NULL AND n.retired_at IS NULL
                   ORDER BY n.kind, n.name, n.canonical_id""",
                (entrance_id,),
            )
            return [self._node(row) for row in cursor.fetchall()]

    def exterior_entrances(self) -> list[CanonicalNode]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT DISTINCT e.* FROM anima_graph_nodes e
                   JOIN anima_graph_relationships r ON r.source_id = e.canonical_id
                   JOIN anima_graph_nodes p ON p.canonical_id = r.target_id
                   WHERE e.kind = 'ENTRANCE' AND p.kind = 'OUTSIDE'
                     AND r.relationship_type = 'CONNECTS' AND r.retired_at IS NULL
                     AND e.retired_at IS NULL ORDER BY e.name, e.canonical_id"""
            )
            return [self._node(row) for row in cursor.fetchall()]

    def related(self, source_id: UUID, relationship_type: RelationshipType) -> list[CanonicalNode]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT n.* FROM anima_graph_nodes n
                   JOIN anima_graph_relationships r ON r.target_id = n.canonical_id
                   WHERE r.source_id = %s AND r.relationship_type = %s
                     AND r.retired_at IS NULL AND n.retired_at IS NULL
                   ORDER BY n.kind, n.name, n.canonical_id""",
                (source_id, relationship_type.value),
            )
            return [self._node(row) for row in cursor.fetchall()]

    def sensors_monitoring(self, target_id: UUID) -> list[CanonicalNode]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT n.* FROM anima_graph_nodes n
                   JOIN anima_graph_relationships r ON r.source_id = n.canonical_id
                   WHERE r.target_id = %s AND r.relationship_type = 'MONITORS'
                     AND r.retired_at IS NULL AND n.kind = 'SENSOR' AND n.retired_at IS NULL
                   ORDER BY n.name, n.canonical_id""",
                (target_id,),
            )
            return [self._node(row) for row in cursor.fetchall()]

    def security_sensitive_resources(self) -> list[CanonicalNode]:
        return self._list_nodes(
            "kind IN ('RESOURCE','SENSOR','ENTRANCE','CAPABILITY') AND security_sensitive"
        )

    def provider_references_for(self, target_id: UUID) -> list[ProviderReference]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM anima_graph_provider_refs WHERE target_id = %s AND retired_at IS NULL ORDER BY provider, external_id",
                (target_id,),
            )
            return [self._provider_reference(row) for row in cursor.fetchall()]

    @staticmethod
    def _provider_reference(row: dict[str, Any]) -> ProviderReference:
        return ProviderReference(
            UUID(str(row["provider_reference_id"])),
            str(row["provider"]),
            str(row["provider_scope"]),
            str(row["external_object_kind"]),
            str(row["external_id"]),
            UUID(str(row["target_id"])),
            TargetKind(str(row["target_kind"])),
            dict(row["metadata"] or {}),
            row["retired_at"],
        )

    def resolve_provider_reference(
        self, provider: str, provider_scope: str, external_object_kind: str, external_id: str
    ) -> CanonicalNode | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT n.* FROM anima_graph_provider_refs p JOIN anima_graph_nodes n ON n.canonical_id = p.target_id
                           WHERE p.provider = %s AND p.provider_scope = %s AND p.external_object_kind = %s
                             AND p.external_id = %s AND p.retired_at IS NULL AND n.retired_at IS NULL""",
                (provider, provider_scope, external_object_kind, external_id),
            )
            row = cursor.fetchone()
        return self._node(row) if row else None

    def resolve_provider_references(
        self, provider: str, provider_scope: str, external_object_kind: str, external_id: str
    ) -> list[CanonicalNode]:
        """Return every active canonical target for one provider identity.

        The singular resolver is convenient for ordinary resource mappings. UI
        authentication needs the cardinality as evidence, so it uses this
        explicit plural form and fails closed on zero or multiple targets.
        """
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT n.* FROM anima_graph_provider_refs p
                           JOIN anima_graph_nodes n ON n.canonical_id = p.target_id
                           WHERE p.provider = %s AND p.provider_scope = %s
                             AND p.external_object_kind = %s AND p.external_id = %s
                             AND p.retired_at IS NULL AND n.retired_at IS NULL
                           ORDER BY n.canonical_id""",
                (provider, provider_scope, external_object_kind, external_id),
            )
            return [self._node(row) for row in cursor.fetchall()]

    def households_for_member(self, member_id: UUID) -> list[CanonicalNode]:
        """Resolve the household(s) containing a canonical person/member."""
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT h.* FROM anima_graph_relationships r
                           JOIN anima_graph_nodes h ON h.canonical_id = r.target_id
                           WHERE r.source_id = %s AND r.relationship_type = 'MEMBER_OF'
                             AND r.retired_at IS NULL AND h.kind = 'HOUSEHOLD'
                             AND h.retired_at IS NULL
                           ORDER BY h.canonical_id""",
                (member_id,),
            )
            return [self._node(row) for row in cursor.fetchall()]

    def members_of_household(self, household_id: UUID) -> list[CanonicalNode]:
        """Return active canonical people whose MEMBER_OF edge targets a household."""
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT p.* FROM anima_graph_relationships r
                           JOIN anima_graph_nodes p ON p.canonical_id = r.source_id
                           WHERE r.target_id = %s AND r.relationship_type = 'MEMBER_OF'
                             AND r.retired_at IS NULL AND p.kind = 'PERSON'
                             AND p.retired_at IS NULL
                           ORDER BY p.name, p.canonical_id""",
                (household_id,),
            )
            return [self._node(row) for row in cursor.fetchall()]

    def resource_capabilities(self, resource_id: UUID) -> list[CanonicalNode]:
        return self.related(resource_id, RelationshipType.EXPOSES)

    def resources_with_capability(self, capability_type: str) -> list[CanonicalNode]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT r.* FROM anima_graph_nodes r JOIN anima_graph_relationships rel ON rel.source_id = r.canonical_id
                           JOIN anima_graph_nodes c ON c.canonical_id = rel.target_id
                           WHERE rel.relationship_type = 'EXPOSES' AND c.kind = 'CAPABILITY'
                             AND c.metadata ->> 'capability_type' = %s AND r.retired_at IS NULL
                           ORDER BY r.kind, r.name, r.canonical_id""",
                (capability_type,),
            )
            return [self._node(row) for row in cursor.fetchall()]

    def resolve_alias(
        self, alias: str, *, scope_id: UUID | None = None, kind: NodeKind | None = None
    ) -> AliasResolution:
        clauses = ["a.normalized_alias = %s", "a.retired_at IS NULL", "n.retired_at IS NULL"]
        params: list[Any] = [normalize_alias(alias)]
        if scope_id is not None:
            clauses.append("(a.scope_id = %s OR a.scope_id IS NULL)")
            params.append(scope_id)
        if kind is not None:
            clauses.append("a.node_kind = %s")
            params.append(kind.value)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""SELECT DISTINCT n.* FROM anima_graph_aliases a
                           JOIN anima_graph_nodes n ON n.canonical_id = a.canonical_id
                           WHERE {" AND ".join(clauses)} ORDER BY n.kind, n.name, n.canonical_id""",
                tuple(params),
            )
            candidates = tuple(self._node(row) for row in cursor.fetchall())
        return AliasResolution(
            alias,
            "NOT_FOUND" if not candidates else "UNIQUE" if len(candidates) == 1 else "AMBIGUOUS",
            candidates,
        )

    def rename_node(
        self, canonical_id: UUID, new_name: str, *, preserve_old_name_as_alias: bool = True
    ) -> None:
        if not new_name.strip():
            raise GraphValidationError("new name must not be empty")
        with self._connect() as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT name, kind FROM anima_graph_nodes WHERE canonical_id = %s AND retired_at IS NULL",
                        (canonical_id,),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise GraphValidationError("cannot rename an unknown or retired node")
                    old_name = str(row["name"])
                    if old_name == new_name:
                        return
                    cursor.execute(
                        "UPDATE anima_graph_nodes SET name = %s, updated_at = now() WHERE canonical_id = %s",
                        (new_name, canonical_id),
                    )
                    if preserve_old_name_as_alias:
                        cursor.execute(
                            "INSERT INTO anima_graph_aliases (alias_id, normalized_alias, display_alias, canonical_id, node_kind) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                            (
                                uuid4(),
                                normalize_alias(old_name),
                                old_name,
                                canonical_id,
                                str(row["kind"]),
                            ),
                        )
                    self._audit(
                        connection,
                        "node.renamed",
                        canonical_id,
                        {"old_name": old_name, "new_name": new_name},
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def move_resource(self, resource_id: UUID, place_id: UUID) -> None:
        """Move one commissioned resource to another canonical place.

        This is an ANIMA topology mutation.  It never changes the provider
        mapping or asks the provider to move a physical device; those remain
        owned by the Home Assistant integration.
        """
        with self._connect() as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT kind FROM anima_graph_nodes WHERE canonical_id = %s AND retired_at IS NULL",
                        (resource_id,),
                    )
                    resource = cursor.fetchone()
                    if resource is None or str(resource["kind"]) not in {"RESOURCE", "SENSOR"}:
                        raise GraphValidationError("resource is unknown or retired")
                    cursor.execute(
                        "SELECT kind FROM anima_graph_nodes WHERE canonical_id = %s AND retired_at IS NULL",
                        (place_id,),
                    )
                    place = cursor.fetchone()
                    if place is None or str(place["kind"]) not in {"ROOM", "ZONE"}:
                        raise GraphValidationError("destination must be an active room or zone")
                    cursor.execute(
                        """SELECT relationship_id, target_id FROM anima_graph_relationships
                           WHERE relationship_type = 'INSTALLED_IN' AND source_id = %s
                             AND retired_at IS NULL ORDER BY relationship_id""",
                        (resource_id,),
                    )
                    current = cursor.fetchall()
                    if len(current) != 1:
                        raise GraphValidationError(
                            "resource must have exactly one active installed-in relationship"
                        )
                    current_place = UUID(str(current[0]["target_id"]))
                    if current_place == place_id:
                        return
                    cursor.execute(
                        "UPDATE anima_graph_relationships SET retired_at = now() WHERE relationship_id = %s",
                        (current[0]["relationship_id"],),
                    )
                    relationship_id = uuid4()
                    cursor.execute(
                        """INSERT INTO anima_graph_relationships
                           (relationship_id, relationship_type, source_id, target_id, metadata)
                           VALUES (%s, 'INSTALLED_IN', %s, %s, '{}'::jsonb)""",
                        (relationship_id, resource_id, place_id),
                    )
                    self._audit(
                        connection,
                        "resource.moved",
                        resource_id,
                        {
                            "from_place_id": str(current_place),
                            "to_place_id": str(place_id),
                            "relationship_id": str(relationship_id),
                        },
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def retire_resource(self, resource_id: UUID) -> None:
        """Retire a commissioned resource and its owned semantic edges."""
        with self._connect() as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT kind FROM anima_graph_nodes WHERE canonical_id = %s AND retired_at IS NULL",
                        (resource_id,),
                    )
                    resource = cursor.fetchone()
                    if resource is None or str(resource["kind"]) not in {"RESOURCE", "SENSOR"}:
                        raise GraphValidationError("resource is unknown or already retired")
                    cursor.execute(
                        """SELECT target_id FROM anima_graph_relationships
                           WHERE relationship_type = 'EXPOSES' AND source_id = %s
                             AND retired_at IS NULL""",
                        (resource_id,),
                    )
                    target_ids = [resource_id] + [
                        UUID(str(row["target_id"])) for row in cursor.fetchall()
                    ]
                    cursor.execute(
                        "UPDATE anima_graph_nodes SET retired_at = now(), updated_at = now() WHERE canonical_id = ANY(%s)",
                        (target_ids,),
                    )
                    cursor.execute(
                        """UPDATE anima_graph_relationships SET retired_at = now()
                           WHERE retired_at IS NULL AND (source_id = ANY(%s) OR target_id = ANY(%s))""",
                        (target_ids, target_ids),
                    )
                    cursor.execute(
                        "UPDATE anima_graph_aliases SET retired_at = now() WHERE retired_at IS NULL AND canonical_id = ANY(%s)",
                        (target_ids,),
                    )
                    cursor.execute(
                        "UPDATE anima_graph_provider_refs SET retired_at = now() WHERE retired_at IS NULL AND target_id = ANY(%s)",
                        (target_ids,),
                    )
                    cursor.execute(
                        "UPDATE anima_graph_truth_bindings SET retired_at = now() WHERE retired_at IS NULL AND target_id = ANY(%s)",
                        (target_ids,),
                    )
                    self._audit(
                        connection,
                        "resource.retired",
                        resource_id,
                        {"retired_target_count": len(target_ids)},
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def map_provider_reference(
        self, reference: ProviderReference, *, allow_remap: bool = False
    ) -> None:
        target = self.get_node(reference.target_id)
        if (
            target is None
            or (
                reference.target_kind == TargetKind.CAPABILITY
                and target.kind != NodeKind.CAPABILITY
            )
            or (reference.target_kind == TargetKind.NODE and target.kind == NodeKind.CAPABILITY)
        ):
            raise GraphValidationError("provider reference target kind is invalid")
        with self._connect() as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """SELECT * FROM anima_graph_provider_refs WHERE provider = %s AND provider_scope = %s AND external_object_kind = %s AND external_id = %s AND retired_at IS NULL""",
                        (
                            reference.provider,
                            reference.provider_scope,
                            reference.external_object_kind,
                            reference.external_id,
                        ),
                    )
                    existing = cursor.fetchone()
                    if existing is not None:
                        existing_target = UUID(str(existing["target_id"]))
                        if existing_target == reference.target_id:
                            return
                        if not allow_remap:
                            raise GraphConflict(
                                "provider reference collision requires allow_remap=True"
                            )
                        cursor.execute(
                            "UPDATE anima_graph_provider_refs SET retired_at = now() WHERE provider_reference_id = %s",
                            (existing["provider_reference_id"],),
                        )
                        self._audit(
                            connection,
                            "provider_reference.retired",
                            UUID(str(existing["provider_reference_id"])),
                            {"replacement_target": str(reference.target_id)},
                        )
                    cursor.execute(
                        """INSERT INTO anima_graph_provider_refs (provider_reference_id, provider, provider_scope, external_object_kind, external_id, target_id, target_kind, metadata) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)""",
                        (
                            reference.provider_reference_id,
                            reference.provider,
                            reference.provider_scope,
                            reference.external_object_kind,
                            reference.external_id,
                            reference.target_id,
                            reference.target_kind.value,
                            self._metadata(reference.metadata),
                        ),
                    )
                    self._audit(
                        connection,
                        "provider_reference.mapped",
                        reference.provider_reference_id,
                        {
                            "target_id": str(reference.target_id),
                            "provider": reference.provider,
                            "external_id": reference.external_id,
                        },
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def retire_node(self, canonical_id: UUID) -> None:
        with self._connect() as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE anima_graph_nodes SET retired_at = now(), updated_at = now() WHERE canonical_id = %s AND retired_at IS NULL",
                        (canonical_id,),
                    )
                    if cursor.rowcount != 1:
                        raise GraphValidationError("node is unknown or already retired")
                    self._audit(connection, "node.retired", canonical_id, {})
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def truth_for_node(
        self, target_id: UUID, truth: TruthReader, *, now: datetime | None = None
    ) -> list[tuple[TruthBinding, TruthResolution]]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM anima_graph_truth_bindings WHERE target_id = %s AND retired_at IS NULL ORDER BY semantic_attribute, truth_key",
                (target_id,),
            )
            bindings = [
                TruthBinding(
                    UUID(str(row["binding_id"])),
                    UUID(str(row["target_id"])),
                    TargetKind(str(row["target_kind"])),
                    str(row["truth_key"]),
                    str(row["semantic_attribute"]),
                    dict(row["metadata"] or {}),
                    row["retired_at"],
                )
                for row in cursor.fetchall()
            ]
        return [(binding, truth.get(binding.truth_key, now=now)) for binding in bindings]

    def people_currently_home(
        self, truth: TruthReader, *, now: datetime | None = None
    ) -> list[dict[str, Any]]:
        people = self._list_nodes("kind = 'PERSON'")
        result: list[dict[str, Any]] = []
        for person in people:
            for binding, resolution in self.truth_for_node(person.canonical_id, truth, now=now):
                if (
                    binding.semantic_attribute == "presence.home"
                    and resolution.status == TruthStatus.CURRENT_KNOWN
                    and resolution.value is True
                ):
                    result.append({"person": person, "binding": binding, "truth": resolution})
        return result

    def audit_events(self) -> list[dict[str, Any]]:
        return self.journal.list_events(event_type="graph.mutation", limit=10000)


def load_commissioning_file(path: Path) -> CommissioningDocument:
    return CommissioningDocument.from_dict(json.loads(path.read_text(encoding="utf-8")))
