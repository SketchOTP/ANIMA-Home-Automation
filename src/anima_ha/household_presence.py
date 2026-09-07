"""Bounded presence context and explicit owner bindings in existing Graph/Truth.

No phone discovery, scans, provider calls, authentication or door-event
attribution. HA person aggregates are not independent tracker corroboration.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from anima_ha.events import (
    DeliveryClass,
    EventEnvelope,
    EventImportance,
    EvidenceKind,
    TruthObservation,
)
from anima_ha.graph import (
    CanonicalNode,
    CanonicalRelationship,
    CommissioningDocument,
    NodeKind,
    ProviderReference,
    RelationshipType,
    TargetKind,
    TruthReader,
)
from anima_ha.plugins import (
    CORE_VERSION,
    MANIFEST_VERSION,
    ExternalContentTrust,
    Idempotency,
    InvocationContext,
    PluginManifest,
    PluginValidationError,
    RuntimeKind,
    TrustClass,
)
from anima_ha.policy import RequestOrigin
from anima_ha.truth import InMemoryTruthState, TruthResolution, TruthStatus


class PresenceError(ValueError):
    """Invalid scope/configuration; errors intentionally contain no provider data."""


class SignalKind(StrEnum):
    GEOFENCE = "GEOFENCE"
    ROUTER_WIFI = "ROUTER_WIFI"
    HA_PERSON = "HA_PERSON"


class PresenceValue(StrEnum):
    HOME = "HOME"
    AWAY = "AWAY"
    NOT_DETECTED = "NOT_DETECTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class PresenceBinding:
    """Projection of explicit private provider-reference metadata, not API input."""

    binding_id: UUID
    household_id: UUID
    person_id: UUID
    resource_id: UUID
    capability_id: UUID
    ha_instance_id: UUID
    signal_kind: SignalKind
    freshness_seconds: int
    version: int
    entity_id: str = field(repr=False)

    def __post_init__(self) -> None:
        if any(
            not isinstance(v, UUID) or not v.int
            for v in (
                self.binding_id,
                self.household_id,
                self.person_id,
                self.resource_id,
                self.capability_id,
                self.ha_instance_id,
            )
        ):
            raise PresenceError("canonical UUIDs required")
        if not isinstance(self.signal_kind, SignalKind):
            raise PresenceError("unsupported presence signal kind")
        domain = "person" if self.signal_kind == SignalKind.HA_PERSON else "device_tracker"
        if (
            not isinstance(self.entity_id, str)
            or len(self.entity_id) > 255
            or not re.fullmatch(domain + r"\.[a-z0-9_]+", self.entity_id)
        ):
            raise PresenceError("source entity does not match signal kind")
        if type(self.freshness_seconds) is not int or not 30 <= self.freshness_seconds <= 86400:
            raise PresenceError("freshness must be 30..86400 seconds")
        if type(self.version) is not int or self.version < 1:
            raise PresenceError("binding version must be positive")

    @property
    def truth_key(self) -> str:
        return f"state/capability/{self.capability_id}/value"


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise PresenceError("timezone-aware time required")
    return value.astimezone(UTC)


def presence_signal(
    binding: PresenceBinding, resolution: TruthResolution, *, now: datetime
) -> dict[str, Any]:
    """Coarse projection only; never serialize Truth values/observations wholesale.

    Freshness is age of the HA observation, not physical location measurement.
    The configured bound can shorten, but never lengthen, existing Truth expiry.
    Named zones/custom states are deliberately UNKNOWN, never emitted as text.
    """
    current = _utc(now)
    if resolution.truth_key != binding.truth_key:
        raise PresenceError("Truth does not match commissioned capability")
    status = resolution.status
    if len(resolution.observations) > 16:
        raise PresenceError("presence observation bound exceeded")
    observed, received = resolution.last_observed_at, resolution.last_received_at
    expires = None
    quality = "HA_STATE_OBSERVATION"
    try:
        observed = _utc(observed) if observed is not None else None
        received = _utc(received) if received is not None else None
        if observed is None or received is None:
            status, quality = TruthStatus.UNKNOWN, "MISSING_TIMESTAMPS"
        elif observed > current or received > current or observed > received:
            status, quality = TruthStatus.UNKNOWN, "CLOCK_SKEW"
        else:
            expires = observed + timedelta(seconds=binding.freshness_seconds)
            if status == TruthStatus.CURRENT_KNOWN and current >= expires:
                status, quality = TruthStatus.STALE, "AGE_LIMIT_EXCEEDED"
    except (PresenceError, OverflowError):
        observed = received = None
        status, quality = TruthStatus.UNKNOWN, "INVALID_TIMESTAMPS"

    value = PresenceValue.UNKNOWN
    if status == TruthStatus.CURRENT_KNOWN:
        expected_source = f"provider:home_assistant:{binding.ha_instance_id}:{binding.entity_id}"
        if (
            resolution.evidence_kind != EvidenceKind.DIRECT
            or not resolution.observations
            or any(o.source != expected_source for o in resolution.observations)
        ):
            status, quality = TruthStatus.UNKNOWN, "UNQUALIFIED_SOURCE_EVIDENCE"
        elif resolution.value == "home":
            value = PresenceValue.HOME
        elif resolution.value == "not_home":
            value = (
                PresenceValue.NOT_DETECTED
                if binding.signal_kind != SignalKind.GEOFENCE
                else PresenceValue.AWAY
            )
        else:
            status, quality = TruthStatus.UNKNOWN, "UNSUPPORTED_COARSE_STATE"
    return {
        "binding_id": str(binding.binding_id),
        "binding_version": binding.version,
        "resource_id": str(binding.resource_id),
        "capability_id": str(binding.capability_id),
        "signal_kind": binding.signal_kind.value,
        "status": status.value,
        "value": value.value,
        "quality": quality,
        "observed_at": observed.isoformat() if observed else None,
        "received_at": received.isoformat() if received else None,
        "expires_at": expires.isoformat() if expires else None,
        "time_basis": "HA_STATE_UPDATED",
        "physical_observed_at": None,
        "independent_tracker": binding.signal_kind != SignalKind.HA_PERSON,
    }


def reduce_presence(signals: list[dict[str, Any]]) -> tuple[TruthStatus, PresenceValue]:
    """Reduce only projections made above, not untrusted model/provider input."""
    if len(signals) > 8:
        raise PresenceError("at most eight presence signals per person")
    # A calculated HA person must not resolve or corroborate its own inputs.
    independent = [s for s in signals if s["independent_tracker"]]
    considered = independent or signals
    values = {s["value"] for s in considered if s["status"] == TruthStatus.CURRENT_KNOWN}
    if (
        any(s["status"] == TruthStatus.CONFLICTING for s in considered)
        or {PresenceValue.HOME, PresenceValue.AWAY} <= values
    ):
        return TruthStatus.CONFLICTING, PresenceValue.UNKNOWN
    if PresenceValue.HOME in values:
        return TruthStatus.CURRENT_KNOWN, PresenceValue.HOME
    if PresenceValue.AWAY in values:
        return TruthStatus.CURRENT_KNOWN, PresenceValue.AWAY
    # Wi-Fi absence alone never establishes household/person absence.
    if PresenceValue.NOT_DETECTED in values:
        return TruthStatus.UNKNOWN, PresenceValue.UNKNOWN
    if any(s["status"] == TruthStatus.STALE for s in considered):
        return TruthStatus.STALE, PresenceValue.UNKNOWN
    if considered and all(s["status"] == TruthStatus.UNAVAILABLE for s in considered):
        return TruthStatus.UNAVAILABLE, PresenceValue.UNKNOWN
    return TruthStatus.UNKNOWN, PresenceValue.UNKNOWN


def router_connection_transition(
    binding: PresenceBinding,
    previous: TruthResolution | None,
    current: TruthResolution,
    *,
    now: datetime,
    previous_binding_version: int | None,
    source_continuous: bool = False,
    recovery: bool = False,
) -> EventEnvelope | None:
    """Project a qualified network edge, never a verified human arrival/departure.

    Core must capture prior Truth before ingestion, and supply positive source
    continuity since that observation. Reset continuity/baseline on startup,
    reconnect, unavailable/unknown, router loss or mapping change. This pure
    function neither journals nor dispatches triggers. Defaults suppress edges.
    """
    if (
        binding.signal_kind != SignalKind.ROUTER_WIFI
        or previous is None
        or previous_binding_version != binding.version
        or source_continuous is not True
        or recovery is not False
    ):
        return None
    before = presence_signal(binding, previous, now=now)
    after = presence_signal(binding, current, now=now)
    if any(s["status"] != TruthStatus.CURRENT_KNOWN for s in (before, after)):
        return None
    # Restored/snapshot data may seed a baseline but is never a new edge.
    for observation in (*previous.observations, *current.observations):
        if any(
            observation.metadata.get(key)
            for key in ("snapshot", "restored", "recovery", "reconcile", "binding_attribution")
        ):
            return None
    if (
        before["value"] == after["value"]
        or previous.last_observed_at is None
        or current.last_observed_at is None
        or current.last_received_at is None
        or previous.last_received_at is None
        or current.last_observed_at <= previous.last_observed_at
        or current.last_received_at < previous.last_received_at
    ):
        return None
    transition = "RECONNECTED" if after["value"] == PresenceValue.HOME else "DISCONNECTED"
    event_id = uuid5(binding.binding_id, f"v{binding.version}:{after['observed_at']}:{transition}")
    return EventEnvelope.create(
        event_id=str(event_id),
        event_type="household.presence.connection_changed",
        source="anima.household_presence",
        subject_key=f"person/{binding.person_id}",
        occurred_at=current.last_observed_at,
        recorded_at=_utc(now),
        payload={
            "household_id": str(binding.household_id),
            "person_id": str(binding.person_id),
            "binding_id": str(binding.binding_id),
            "binding_version": binding.version,
            "resource_id": str(binding.resource_id),
            "capability_id": str(binding.capability_id),
            "signal_kind": binding.signal_kind.value,
            "transition": transition,
            "value": after["value"],
            "observed_at": after["observed_at"],
            "received_at": after["received_at"],
            "previous_observed_at": before["observed_at"],
            "time_basis": "HA_STATE_UPDATED",
            "physical_observed_at": None,
            "is_authentication": False,
            "door_actor_verified": False,
            "evidence_basis": "ASSOCIATED_DEVICE_REPORTS",
            "external_content_trust": "EXTERNAL_UNTRUSTED",
        },
        evidence_kind=EvidenceKind.DIRECT,
        delivery_class=DeliveryClass.GUARANTEED,
        importance=EventImportance.NORMAL,
        metadata={
            "external_content_trust": "EXTERNAL_UNTRUSTED",
            "household_id": str(binding.household_id),
        },
    )


def normalized_router_connection_events(
    event: EventEnvelope,
    bindings: list[PresenceBinding],
    previous_by_binding: dict[UUID, tuple[int, TruthResolution]],
    *,
    now: datetime,
    source_continuous: bool = False,
    recovery: bool = False,
) -> tuple[list[EventEnvelope], dict[UUID, tuple[int, TruthResolution]]]:
    """Adapter callback projection + replacement volatile baseline (max 8 matches).

    Supply only bindings returned by service.bindings_for_event. Store returned
    baselines for these bindings, *replacing* their prior entries (empty resets).
    Clear ALL baselines on transport/router loss, startup and reconciliation.
    No Journal write, attention dispatch, or provider calls occur here.
    """
    if len(bindings) > 8 or len(previous_by_binding) > 8:
        raise PresenceError("event binding bound exceeded")
    if event.event_type != "truth.observation":
        return [], {}
    if any(
        event.metadata.get(k)
        for k in ("snapshot", "restored", "recovery", "reconcile", "binding_attribution")
    ):
        return [], {}
    try:
        observation = TruthObservation.from_payload(event.payload, event_id=event.event_id)
        source_uuid = UUID(event.event_id)
        # The generic HA parser can fall back to receipt time. Never treat that
        # fallback as a genuine HA source timestamp for a network edge.
        source_updated = datetime.fromisoformat(str(observation.metadata["last_updated"]))
        if _utc(source_updated) != observation.observed_at:
            return [], {}
    except (ValueError, TypeError, KeyError, OverflowError):
        return [], {}
    if any(
        observation.metadata.get(k)
        for k in ("snapshot", "restored", "recovery", "reconcile", "binding_attribution")
    ):
        return [], {}
    truth = InMemoryTruthState()
    truth.add(observation)
    current = truth.get(observation.truth_key, now=_utc(now))
    result = []
    baselines = {}
    for binding in {b.binding_id: b for b in bindings}.values():
        if (
            binding.signal_kind != SignalKind.ROUTER_WIFI
            or observation.truth_key != binding.truth_key
            or event.source != f"provider:home_assistant:{binding.ha_instance_id}"
        ):
            continue
        if presence_signal(binding, current, now=now)["status"] != TruthStatus.CURRENT_KNOWN:
            continue
        prior = previous_by_binding.get(binding.binding_id)
        if (
            prior is not None
            and prior[1].last_observed_at is not None
            and observation.observed_at <= prior[1].last_observed_at
        ):
            # Duplicate or delayed data cannot move a known baseline backwards.
            baselines[binding.binding_id] = prior
            continue
        # Retain only the coarse observation, never raw attributes/locations/MAC.
        clean = replace(observation, metadata={})
        clean_truth = InMemoryTruthState()
        clean_truth.add(clean)
        baselines[binding.binding_id] = (
            binding.version,
            clean_truth.get(binding.truth_key, now=now),
        )
        edge = router_connection_transition(
            binding,
            prior[1] if prior else None,
            current,
            now=now,
            previous_binding_version=prior[0] if prior else None,
            source_continuous=source_continuous,
            recovery=recovery,
        )
        if edge is not None:
            result.append(
                replace(
                    edge,
                    event_id=str(uuid5(binding.binding_id, f"v{binding.version}:{source_uuid}")),
                    causation_id=str(source_uuid),
                )
            )
    return result, baselines


class PresenceGraph(Protocol):
    def commission(self, document: CommissioningDocument) -> Any: ...
    def get_node(self, canonical_id: UUID) -> CanonicalNode | None: ...
    def members_of_household(self, household_id: UUID) -> list[CanonicalNode]: ...
    def resources_in_place(self, place_id: UUID, recursive: bool = True) -> list[CanonicalNode]: ...
    def related(
        self, source_id: UUID, relationship_type: RelationshipType
    ) -> list[CanonicalNode]: ...
    def resource_capabilities(self, resource_id: UUID) -> list[CanonicalNode]: ...
    def provider_references_for(self, target_id: UUID) -> list[ProviderReference]: ...


class HouseholdPresenceService:
    """Only explicit owner binding persists; no provider mutation.

    Bindings require PERSON ASSOCIATED_WITH resource, resource EXPOSES capability,
    household installation, and that capability's HA entity provider reference.
    An additional private ANIMA reference holds explicit binding metadata; the
    original HA provider reference remains untouched. Classification is injected
    by Core, never accepted from model input. None means not qualified.
    """

    def __init__(
        self,
        graph: PresenceGraph,
        truth: TruthReader,
        *,
        classify_source: Callable[[ProviderReference], SignalKind | None] | None = None,
    ) -> None:
        self.graph, self.truth = graph, truth
        self.classify_source = classify_source or (lambda ref: None)

    def _bindings(
        self, household_id: UUID, person_id: UUID, instance_id: UUID, resources: set[UUID]
    ) -> list[PresenceBinding]:
        associated = self.graph.related(person_id, RelationshipType.ASSOCIATED_WITH)
        if len(associated) > 8:
            raise PresenceError("associated resource bound exceeded")
        bindings: dict[UUID, PresenceBinding] = {}
        source_keys: set[tuple[str, str]] = set()
        capability_keys: set[UUID] = set()
        for resource in {n.canonical_id: n for n in associated}.values():
            if resource.retired_at is not None:
                continue
            if resource.canonical_id not in resources or resource.kind not in {
                NodeKind.RESOURCE,
                NodeKind.SENSOR,
            }:
                raise PresenceError("associated resource is outside household")
            capabilities = self.graph.resource_capabilities(resource.canonical_id)
            if len(capabilities) > 64:
                raise PresenceError("resource capability bound exceeded")
            for capability in {n.canonical_id: n for n in capabilities}.values():
                if capability.kind != NodeKind.CAPABILITY or capability.retired_at is not None:
                    continue
                references = self.graph.provider_references_for(capability.canonical_id)
                if len(references) > 16:
                    raise PresenceError("provider reference bound exceeded")
                for ref in references:
                    if ref.provider != "anima.household_presence":
                        continue
                    config = ref.metadata.get("household_presence")
                    if config is None or ref.retired_at is not None:
                        continue
                    if (
                        not isinstance(config, dict)
                        or type(config.get("schema_version")) is not int
                        or config.get("schema_version") != 1
                        or config.get("household_id") != str(household_id)
                        or config.get("person_id") != str(person_id)
                        or config.get("home_semantics_verified") is not True
                        or ref.provider_scope != str(household_id)
                        or ref.external_object_kind != "binding"
                        or ref.external_id != str(capability.canonical_id)
                        or ref.target_id != capability.canonical_id
                        or ref.target_kind.value != "CAPABILITY"
                    ):
                        raise PresenceError("presence binding metadata or scope is invalid")
                    originals = {
                        r.provider_reference_id: r
                        for r in references
                        if str(r.provider_reference_id) == config.get("ha_reference_id")
                        and r.provider == "home_assistant"
                        and r.provider_scope == str(instance_id)
                        and r.external_object_kind == "entity"
                        and r.target_id == capability.canonical_id
                        and r.target_kind == TargetKind.CAPABILITY
                        and r.retired_at is None
                    }
                    if len(originals) != 1:
                        raise PresenceError("original HA reference is not active in scope")
                    original = next(iter(originals.values()))
                    try:
                        binding = PresenceBinding(
                            ref.provider_reference_id,
                            household_id,
                            person_id,
                            resource.canonical_id,
                            capability.canonical_id,
                            instance_id,
                            SignalKind(config["signal_kind"]),
                            config["freshness_seconds"],
                            config["version"],
                            original.external_id,
                        )
                    except (KeyError, TypeError, ValueError):
                        raise PresenceError("presence binding configuration is invalid") from None
                    if binding.binding_id in bindings:
                        if binding != bindings[binding.binding_id]:
                            raise PresenceError("ambiguous duplicate presence binding")
                        continue
                    source_key = (original.provider_scope, original.external_id)
                    if source_key in source_keys or capability.canonical_id in capability_keys:
                        raise PresenceError("presence source or capability is ambiguous")
                    source_keys.add(source_key)
                    capability_keys.add(capability.canonical_id)
                    bindings[binding.binding_id] = binding
                    if len(bindings) > 8:
                        raise PresenceError("at most eight presence signals per person")
        return sorted(bindings.values(), key=lambda b: b.binding_id)

    def _scope(self, household_id: UUID) -> tuple[CanonicalNode, dict[UUID, CanonicalNode]]:
        root = self.graph.get_node(household_id)
        if root is None or root.kind != NodeKind.HOUSEHOLD or root.retired_at is not None:
            raise PresenceError("household is not active")
        members = self.graph.members_of_household(household_id)
        if len(members) > 256:
            raise PresenceError("household member bound exceeded")
        return root, {
            n.canonical_id: n for n in members if n.kind == NodeKind.PERSON and n.retired_at is None
        }

    def _sources(
        self,
        household_id: UUID,
        instance_id: UUID,
    ) -> dict[UUID, tuple[CanonicalNode, CanonicalNode, ProviderReference, SignalKind]]:
        self._scope(household_id)
        resources = self.graph.resources_in_place(household_id)
        if len(resources) > 4096:
            raise PresenceError("household resource bound exceeded")
        result: dict[UUID, tuple[CanonicalNode, CanonicalNode, ProviderReference, SignalKind]] = {}
        inspected = 0
        for resource in {r.canonical_id: r for r in resources}.values():
            if resource.retired_at is not None or resource.kind not in {
                NodeKind.RESOURCE,
                NodeKind.SENSOR,
            }:
                continue
            caps = self.graph.resource_capabilities(resource.canonical_id)
            inspected += len(caps)
            if len(caps) > 64 or inspected > 4096:
                raise PresenceError("capability inspection bound exceeded")
            for cap in {c.canonical_id: c for c in caps}.values():
                if cap.retired_at is not None or cap.kind != NodeKind.CAPABILITY:
                    continue
                refs = self.graph.provider_references_for(cap.canonical_id)
                if len(refs) > 16:
                    raise PresenceError("provider reference bound exceeded")
                for ref in refs:
                    if (
                        ref.retired_at is not None
                        or ref.provider != "home_assistant"
                        or ref.provider_scope != str(instance_id)
                        or ref.external_object_kind != "entity"
                        or ref.target_id != cap.canonical_id
                        or ref.target_kind != TargetKind.CAPABILITY
                    ):
                        continue
                    kind = self.classify_source(ref)
                    if kind is None:
                        continue
                    if not isinstance(kind, SignalKind):
                        raise PresenceError("invalid trusted source classification")
                    domain = "person" if kind == SignalKind.HA_PERSON else "device_tracker"
                    if len(ref.external_id) > 255 or not re.fullmatch(
                        domain + r"\.[a-z0-9_]+", ref.external_id
                    ):
                        raise PresenceError("classified source domain mismatch")
                    handle = uuid5(
                        NAMESPACE_URL,
                        f"anima:presence-source:{household_id}:{instance_id}:{ref.provider_reference_id}",
                    )
                    candidate = (resource, cap, ref, kind)
                    if handle in result and result[handle] != candidate:
                        raise PresenceError("ambiguous commissioned presence source")
                    result[handle] = candidate
                    if len(result) > 256:
                        raise PresenceError("presence source bound exceeded")
        return result

    def list_sources(
        self,
        household_id: UUID,
        *,
        ha_instance_id: UUID,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Commissioned qualified handles only, not an HA entity/MAC inventory."""
        if type(limit) is not int or not 1 <= limit <= 50:
            raise PresenceError("limit must be 1..50")
        sources = self._sources(household_id, ha_instance_id)
        prefix = f"presence-sources-v1/{household_id}/{ha_instance_id}/"
        after = -1
        if cursor is not None:
            if not isinstance(cursor, str) or len(cursor) > 200 or not cursor.startswith(prefix):
                raise PresenceError("source cursor is invalid for scope")
            try:
                after = UUID(cursor[len(prefix) :]).int
            except ValueError:
                raise PresenceError("source cursor position is invalid") from None
        selected = [key for key in sorted(sources) if key.int > after]
        return {
            "schema_version": 1,
            "items": [
                {
                    "source_handle": str(key),
                    "resource_id": str(sources[key][0].canonical_id),
                    "capability_id": str(sources[key][1].canonical_id),
                    "signal_kind": sources[key][3].value,
                }
                for key in selected[:limit]
            ],
            "next_cursor": prefix + str(selected[limit - 1]) if len(selected) > limit else None,
            "source_status": "QUALIFIED_SOURCES" if sources else "NO_QUALIFIED_COMMISSIONED_SOURCE",
        }

    def bindings_for_event(
        self,
        household_id: UUID,
        *,
        ha_instance_id: UUID,
        event: EventEnvelope,
    ) -> list[PresenceBinding]:
        """Private Core-only matching; returned bindings must never be serialized."""
        if (
            event.event_type != "truth.observation"
            or event.source != f"provider:home_assistant:{ha_instance_id}"
        ):
            return []
        _, people = self._scope(household_id)
        resources = self.graph.resources_in_place(household_id)
        if len(resources) > 4096:
            raise PresenceError("household resource bound exceeded")
        ids = {r.canonical_id for r in resources if r.retired_at is None}
        result = {}
        for person_id in people:
            for b in self._bindings(household_id, person_id, ha_instance_id, ids):
                if (
                    b.truth_key == event.payload.get("truth_key")
                    and b.signal_kind == SignalKind.ROUTER_WIFI
                ):
                    result[b.binding_id] = b
                    if len(result) > 8:
                        raise PresenceError("event binding bound exceeded")
        return [result[key] for key in sorted(result)]

    def bind_source(
        self,
        context: InvocationContext,
        *,
        ha_instance_id: UUID,
        person_id: UUID,
        source_handle: UUID,
        freshness_seconds: int,
    ) -> dict[str, Any]:
        """Owner-associate an existing qualified source; never commission a phone.

        Mapping changes are deliberately not supported: a conflicting assignment
        requires a separately authorized correction workflow, not silent overwrite.
        """
        root, people = self._scope(context.household_id)
        owner = people.get(context.principal_id) if context.principal_id else None
        if (
            owner is None
            or owner.metadata.get("semantic_role") != "owner"
            or context.origin != RequestOrigin.DIRECT_USER
        ):
            raise PresenceError("direct commissioned owner required")
        person = people.get(person_id)
        if person is None:
            raise PresenceError("person is not an active household member")
        candidate = self._sources(context.household_id, ha_instance_id).get(source_handle)
        if candidate is None:
            raise PresenceError("qualified commissioned source handle required")
        resource, cap, original, kind = candidate
        binding_id = uuid5(
            NAMESPACE_URL, f"anima:presence-binding:{context.household_id}:{cap.canonical_id}"
        )
        binding = PresenceBinding(
            binding_id,
            context.household_id,
            person_id,
            resource.canonical_id,
            cap.canonical_id,
            ha_instance_id,
            kind,
            freshness_seconds,
            1,
            original.external_id,
        )
        # One resource's explicit owner mapping must not silently transfer people.
        for other in people:
            associated = self.graph.related(other, RelationshipType.ASSOCIATED_WITH)
            if len(associated) > 8:
                raise PresenceError("associated resource bound exceeded")
            if (
                other == person_id
                and len(associated) >= 8
                and all(n.canonical_id != resource.canonical_id for n in associated)
            ):
                raise PresenceError("associated resource bound exceeded")
            if other != person_id and any(
                n.canonical_id == resource.canonical_id for n in associated
            ):
                raise PresenceError("resource is already associated with another person")
        existing = self._bindings(
            context.household_id,
            person_id,
            ha_instance_id,
            {n.canonical_id for n in self.graph.resources_in_place(context.household_id)},
        )
        if len(existing) >= 8 and all(b.binding_id != binding_id for b in existing):
            raise PresenceError("at most eight presence signals per person")
        refs = self.graph.provider_references_for(cap.canonical_id)
        for ref in refs:
            if ref.provider == "anima.household_presence":
                matches = [b for b in existing if b.binding_id == ref.provider_reference_id]
                if matches == [binding]:
                    return {
                        "status": "SUCCEEDED",
                        "binding_id": str(binding_id),
                        "binding_version": 1,
                    }
                raise PresenceError("existing binding requires explicit correction")
        if len(refs) >= 16:
            raise PresenceError("provider reference bound exceeded")
        private_ref = ProviderReference(
            binding_id,
            "anima.household_presence",
            str(context.household_id),
            "binding",
            str(cap.canonical_id),
            cap.canonical_id,
            TargetKind.CAPABILITY,
            {
                "household_presence": {
                    "schema_version": 1,
                    "household_id": str(context.household_id),
                    "person_id": str(person_id),
                    "ha_reference_id": str(original.provider_reference_id),
                    "signal_kind": kind.value,
                    "freshness_seconds": freshness_seconds,
                    "version": 1,
                    "home_semantics_verified": True,
                    "commissioned_by": str(context.principal_id),
                }
            },
        )
        edge = CanonicalRelationship(
            uuid5(NAMESPACE_URL, f"anima:presence-association:{person_id}:{resource.canonical_id}"),
            RelationshipType.ASSOCIATED_WITH,
            person_id,
            resource.canonical_id,
        )
        self.graph.commission(
            CommissioningDocument(
                version=1,
                nodes=(root, person, resource, cap),
                relationships=(edge,),
                provider_references=(private_ref,),
            )
        )
        # Graph preserves existing refs rather than overwriting metadata; verify
        # the committed assignment, including a competing commissioning request.
        actual = self._bindings(
            context.household_id,
            person_id,
            ha_instance_id,
            {resource.canonical_id} | {b.resource_id for b in existing},
        )
        if binding not in actual:
            raise PresenceError("binding persistence could not be confirmed")
        return {"status": "SUCCEEDED", "binding_id": str(binding_id), "binding_version": 1}

    def snapshot(
        self,
        household_id: UUID,
        *,
        ha_instance_id: UUID,
        now: datetime,
        person_id: UUID | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Trusted Core scope only; stable UUID keyset, maximum 50 people/page."""
        current = _utc(now)
        if not isinstance(household_id, UUID) or not isinstance(ha_instance_id, UUID):
            raise PresenceError("trusted household and instance UUIDs required")
        if type(limit) is not int or not 1 <= limit <= 50:
            raise PresenceError("limit must be 1..50")
        root = self.graph.get_node(household_id)
        if root is None or root.kind != NodeKind.HOUSEHOLD or root.retired_at is not None:
            raise PresenceError("household is not active")
        members = self.graph.members_of_household(household_id)
        if len(members) > 256:
            raise PresenceError("household member bound exceeded")
        people = {
            n.canonical_id: n for n in members if n.kind == NodeKind.PERSON and n.retired_at is None
        }
        if person_id is not None and person_id not in people:
            raise PresenceError("person is not an active household member")
        prefix = f"presence-v1/{household_id}/{ha_instance_id}/{person_id or 'all'}/"
        after = -1
        if cursor is not None:
            if not isinstance(cursor, str) or len(cursor) > 200 or not cursor.startswith(prefix):
                raise PresenceError("presence cursor is invalid for scope")
            try:
                after = UUID(cursor[len(prefix) :]).int
            except ValueError:
                raise PresenceError("presence cursor position is invalid") from None
        selected = [
            key
            for key in sorted(people)
            if key.int > after and (person_id is None or key == person_id)
        ]
        resource_nodes = self.graph.resources_in_place(household_id)
        if len(resource_nodes) > 4096:
            raise PresenceError("household resource bound exceeded")
        resources = {n.canonical_id for n in resource_nodes if n.retired_at is None}
        items = []
        for key in selected[:limit]:
            bindings = self._bindings(household_id, key, ha_instance_id, resources)
            signals = [
                presence_signal(b, self.truth.get(b.truth_key, now=current), now=current)
                for b in bindings
            ]
            status, value = reduce_presence(signals)
            items.append(
                {
                    "person_id": str(key),
                    "status": status.value,
                    "value": value.value,
                    "binding_status": "CONFIGURED" if bindings else "UNCONFIGURED",
                    "signals": signals,
                    "is_authentication": False,
                    "door_actor_verified": False,
                    "evidence_basis": "ASSOCIATED_DEVICE_REPORTS",
                }
            )
        return {
            "schema_version": 1,
            "household_id": str(household_id),
            "as_of": current.isoformat(),
            "items": items,
            "next_cursor": prefix + str(selected[limit - 1]) if len(selected) > limit else None,
            "external_content_trust": "EXTERNAL_UNTRUSTED",
        }


class HouseholdPresenceNativePlugin:
    def __init__(
        self,
        service: HouseholdPresenceService,
        ha_instance_id: UUID,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(ha_instance_id, UUID) or not ha_instance_id.int:
            raise PresenceError("trusted HA instance UUID required")
        self.service, self.ha_instance_id = service, ha_instance_id
        self.now = now or (lambda: datetime.now(UTC))

    def start(self, secret_env: dict[str, str]) -> None:
        del secret_env

    def stop(self) -> None:
        return None

    def list_tools(self) -> list[dict[str, Any]]:
        return [dict(item) for item in HOUSEHOLD_PRESENCE_MANIFEST.tools]

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        raise PluginValidationError("household-presence requires trusted invocation context")

    def invoke_with_invocation_context(
        self,
        name: str,
        arguments: dict[str, Any],
        timeout: float,
        context: InvocationContext,
    ) -> dict[str, Any]:
        del timeout
        allowed = {
            "snapshot": {"person_id", "limit", "cursor"},
            "list_sources": {"limit", "cursor"},
            "bind_source": {"person_id", "source_handle", "freshness_seconds"},
        }
        if name not in allowed or arguments.keys() - allowed[name]:
            raise PluginValidationError("unsupported presence tool or argument")
        args = dict(arguments)
        try:
            for key in ("person_id", "source_handle"):
                if key in args:
                    args[key] = UUID(str(args[key]))
        except ValueError:
            raise PresenceError("canonical UUID required") from None
        if name == "snapshot":
            return self.service.snapshot(
                context.household_id, ha_instance_id=self.ha_instance_id, now=self.now(), **args
            )
        if name == "list_sources":
            return self.service.list_sources(
                context.household_id, ha_instance_id=self.ha_instance_id, **args
            )
        if args.keys() != allowed["bind_source"]:
            raise PresenceError("person, source handle and freshness required")
        return self.service.bind_source(context, ha_instance_id=self.ha_instance_id, **args)


_PAGE_SCHEMA = {
    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
    "cursor": {"type": "string", "minLength": 1, "maxLength": 200},
}
_UUID_SCHEMA = {"type": "string", "format": "uuid"}
HOUSEHOLD_PRESENCE_MANIFEST = PluginManifest(
    plugin_id="anima.household-presence",
    plugin_version="1.0.0",
    manifest_version=MANIFEST_VERSION,
    requires_core=CORE_VERSION,
    name="Household presence",
    description="Coarse device evidence, never authentication or door attribution",
    runtime_kind=RuntimeKind.TRUSTED_NATIVE,
    trust_class=TrustClass.TRUSTED_NATIVE,
    capabilities=("household.presence",),
    source="builtin:anima_ha.household_presence",
    events=("household.presence.connection_changed",),
    tools=tuple(
        {
            "name": name,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "items": {"type": "array", "maxItems": 50, "items": {"type": "object"}},
                    "next_cursor": {"type": ["string", "null"], "maxLength": 200},
                    "status": {"type": "string"},
                },
                "additionalProperties": True,
            },
            "semantic_action": "capabilities.configure"
            if name == "bind_source"
            else "capabilities.read",
            "risk_class": "SECURITY_SECURE_ACTION" if name == "bind_source" else "READ_ONLY",
            "read_only": name != "bind_source",
            "idempotency": (
                Idempotency.KEYED if name == "bind_source" else Idempotency.IDEMPOTENT
            ).value,
            "external_content_trust": ExternalContentTrust.EXTERNAL_UNTRUSTED.value,
        }
        for name, description, properties, required in (
            (
                "snapshot",
                "Read bounded coarse presence evidence; never identify who opened a door",
                {**_PAGE_SCHEMA, "person_id": _UUID_SCHEMA},
                [],
            ),
            (
                "list_sources",
                "List opaque commissioned presence sources; no entity IDs or MAC addresses",
                _PAGE_SCHEMA,
                [],
            ),
            (
                "bind_source",
                "Direct owner assignment of an existing qualified source to a household person",
                {
                    "person_id": _UUID_SCHEMA,
                    "source_handle": _UUID_SCHEMA,
                    "freshness_seconds": {"type": "integer", "minimum": 30, "maximum": 86400},
                },
                ["person_id", "source_handle", "freshness_seconds"],
            ),
        )
    ),
)
