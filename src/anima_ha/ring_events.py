"""HA Ring event entities → sparse canonical Journal events, no video or authority."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from anima_ha.events import DeliveryClass, EventEnvelope, EvidenceKind
from anima_ha.graph import NodeKind, TargetKind

_TYPES = {"ring": "doorbell", "motion": "motion", "intercom_unlock": "intercom_unlock"}


class RingEventRouter:
    def __init__(
        self,
        adapter: Any,
        household_id: UUID,
        journal: Any,
        *,
        continuity: Callable[[], tuple[bool, Any, datetime]],
        dispatch: Callable[[EventEnvelope, int], None] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.adapter, self.household_id, self.journal = adapter, household_id, journal
        self.continuity, self.dispatch = continuity, dispatch
        self.now = now or (lambda: datetime.now(UTC))
        self._lock = Lock()
        self._epoch: Any = None
        self._latest: dict[str, datetime] = {}
        self._pending: dict[str, EventEnvelope] = {}

    def _mapping(self, entity_id: str) -> tuple[UUID, UUID] | None:
        inventory = self.adapter.provider_inventory()
        if len(inventory) > 10000:
            return None
        matches = [
            row
            for row in inventory
            if row.get("external_object_kind") == "entity"
            and row.get("external_id") == entity_id
            and row.get("present")
            and row.get("metadata", {}).get("platform") == "ring"
            and not row.get("metadata", {}).get("disabled_by")
        ]
        if len(matches) != 1:
            return None
        graph = self.adapter.graph
        household = graph.get_node(self.household_id)
        if household is None or household.kind != NodeKind.HOUSEHOLD or household.retired_at:
            return None
        scope = self.adapter.config.provider_scope
        targets = graph.resolve_provider_references("home_assistant", scope, "entity", entity_id)
        if len(targets) != 1 or targets[0].kind != NodeKind.CAPABILITY or targets[0].retired_at:
            return None
        cap = targets[0]
        refs = graph.provider_references_for(cap.canonical_id)
        if not any(
            ref.provider == "home_assistant"
            and ref.provider_scope == scope
            and ref.external_object_kind == "entity"
            and ref.external_id == entity_id
            and ref.target_kind == TargetKind.CAPABILITY
            and ref.target_id == cap.canonical_id
            and ref.retired_at is None
            for ref in refs
        ):
            return None
        owners = [
            resource
            for resource in graph.resources_in_place(self.household_id)
            if resource.retired_at is None
            and resource.kind in {NodeKind.SENSOR, NodeKind.RESOURCE}
            and any(
                c.canonical_id == cap.canonical_id
                for c in graph.resource_capabilities(resource.canonical_id)
            )
        ]
        return (owners[0].canonical_id, cap.canonical_id) if len(owners) == 1 else None

    def handle(self, event: EventEnvelope) -> list[str]:
        entity_id = event.metadata.get("external_id")
        scope = self.adapter.config.provider_scope
        if (
            event.event_type != "truth.observation"
            or not isinstance(entity_id, str)
            or not entity_id.startswith("event.")
            or event.metadata.get("snapshot")
            or event.source != f"provider:home_assistant:{scope}"
            or event.metadata.get("provider_scope") != scope
        ):
            return []
        data = event.payload
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict) or any(
            metadata.get(k)
            for k in ("snapshot", "restored", "recovery", "reconcile", "binding_attribution")
        ):
            return []
        attrs = metadata.get("attributes", {})
        event_type = attrs.get("event_type") if isinstance(attrs, dict) else None
        kind = _TYPES.get(event_type) if isinstance(event_type, str) else None
        if kind is None:
            return []
        try:
            occurred = datetime.fromisoformat(str(data["value"]))
            if occurred.tzinfo is None:
                return []
            occurred = occurred.astimezone(UTC)
        except (KeyError, ValueError):
            return []
        with self._lock:
            online, epoch, ready_at = self.continuity()
            now = self.now()
            if epoch != self._epoch or not online:
                self._latest.clear()
                self._pending.clear()
                self._epoch = epoch
            if (
                not online
                or not isinstance(ready_at, datetime)
                or ready_at.tzinfo is None
                or occurred <= ready_at
                or occurred > now
                or (now - occurred).total_seconds() > 120
                or occurred <= self._latest.get(entity_id, ready_at)
            ):
                return []
            mapping = self._mapping(entity_id)
            if mapping is None:
                return []
            resource_id, capability_id = mapping
            event_id = str(
                uuid5(
                    NAMESPACE_URL, f"anima:ring:{scope}:{entity_id}:{occurred.isoformat()}:{kind}"
                )
            )
            derived = EventEnvelope.create(
                event_id=event_id,
                source="anima.ring",
                event_type=f"household.ring.{kind}",
                subject_key=f"resource/{resource_id}",
                occurred_at=occurred,
                recorded_at=now,
                causation_id=event.event_id,
                payload={
                    "household_id": str(self.household_id),
                    "resource_id": str(resource_id),
                    "capability_id": str(capability_id),
                    "occurred_at": occurred.isoformat(),
                    "received_at": now.isoformat(),
                    "physical_occurred_at": None,
                    "time_basis": "HA_EVENT_RECEIVED",
                    "temporal_uncertainty": True,
                    "physical_actor_verified": False,
                    "external_content_trust": "EXTERNAL_UNTRUSTED",
                },
                metadata={
                    "household_id": str(self.household_id),
                    "external_content_trust": "EXTERNAL_UNTRUSTED",
                },
                evidence_kind=EvidenceKind.DIRECT,
                delivery_class=DeliveryClass.GUARANTEED,
            )
            # Preserve receipt time/content across an interrupted append/dispatch retry.
            if len(self._pending) >= 2048 and entity_id not in self._pending:
                return []
            derived = self._pending.setdefault(entity_id, derived)
            if derived.event_id != event_id:
                raise RuntimeError("RING_PENDING_EVENT_REQUIRES_RETRY")
            appended = self.journal.append(derived)
            if self.dispatch is not None:
                self.dispatch(derived, appended.journal_position)
            # Advance only after append+exact dispatch; an interrupted retry uses same event ID.
            if len(self._latest) >= 2048 and entity_id not in self._latest:
                self._latest.clear()
            self._latest[entity_id] = occurred
            self._pending.pop(entity_id, None)
            return [event_id]
