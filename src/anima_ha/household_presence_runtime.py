"""Core-owned connection-event routing; no speech, identity or location inference."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import UUID

from anima_ha.events import EventEnvelope
from anima_ha.household_presence import (
    HouseholdPresenceService,
    normalized_router_connection_events,
)
from anima_ha.truth import TruthResolution


class HouseholdPresenceEventRouter:
    def __init__(
        self,
        service: HouseholdPresenceService,
        household_id: UUID,
        ha_instance_id: UUID,
        *,
        continuity: Callable[[], tuple[bool, Any]],
        journal: Any,
        dispatch: Callable[[EventEnvelope, int], None],
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.service = service
        self.household_id = household_id
        self.ha_instance_id = ha_instance_id
        self.continuity = continuity
        self.journal = journal
        self.dispatch = dispatch
        self.now = now or (lambda: datetime.now(UTC))
        self._epoch: Any = None
        self._baselines: dict[UUID, tuple[int, TruthResolution]] = {}
        self._lock = Lock()

    def handle(self, event: EventEnvelope) -> list[str]:
        # This is a private adapter callback, not model-controlled HTTP input.
        # Unrelated HA traffic must not run a household-wide source lookup.
        if not str(event.metadata.get("external_id", "")).startswith("device_tracker."):
            return []
        with self._lock:
            online, epoch = self.continuity()
            if not online or epoch != self._epoch:
                self._baselines.clear()
                self._epoch = epoch
            if not online:
                return []
            bindings = self.service.bindings_for_event(
                self.household_id, ha_instance_id=self.ha_instance_id, event=event
            )
            before = {
                b.binding_id: self._baselines[b.binding_id]
                for b in bindings
                if b.binding_id in self._baselines
            }
            events, baselines = normalized_router_connection_events(
                event, bindings, before, now=self.now(), source_continuous=True
            )
            emitted = []
            for edge in events:
                appended = self.journal.append(edge)
                self.dispatch(edge, appended.journal_position)
                emitted.append(edge.event_id)
            # Keep the prior observation if append/dispatch fails. A retry of
            # this source event must reach the same deterministic edge identity
            # (Journal and IntelligenceRequest deduplication remain authoritative).
            for binding in bindings:
                self._baselines.pop(binding.binding_id, None)
            self._baselines.update(baselines)
            if len(self._baselines) > 2048:
                self._baselines.clear()
                raise RuntimeError("HOUSEHOLD_PRESENCE_BASELINE_LIMIT")
            return emitted
