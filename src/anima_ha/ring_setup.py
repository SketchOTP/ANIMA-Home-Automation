"""Owner UI-only Ring account setup through HA 2026.9 config flows.

No NativePlugin, MCP tool, credential store or generic invocation audit. HA owns
its account/token and 2FA flow. ANIMA keeps only scoped flow IDs for ten minutes.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from threading import RLock
from typing import Any
from uuid import UUID, uuid4

from anima_ha.graph import NodeKind


class RingSetupError(RuntimeError):
    pass


@dataclass
class _Flow:
    principal_id: UUID
    connection: Any
    ha_id: str
    step: str
    expires: float


class RingSetupService:
    def __init__(self, adapter: Any, household_id: UUID) -> None:
        self.adapter = adapter
        self.household_id = household_id
        self._flows: dict[str, _Flow] = {}
        self._lock = RLock()
        self._configured = False

    def can_edit(self, identity: Any) -> bool:
        if identity.household_id != self.household_id or self.adapter is None:
            return False
        graph = self.adapter.graph
        household = graph.get_node(self.household_id)
        if household is None or household.kind != NodeKind.HOUSEHOLD or household.retired_at:
            return False
        person = graph.get_node(identity.principal_id)
        return bool(
            person
            and person.kind == NodeKind.PERSON
            and person.retired_at is None
            and person.metadata.get("semantic_role") == "owner"
            and any(
                p.canonical_id == identity.principal_id
                for p in graph.members_of_household(self.household_id)
            )
        )

    def require_owner(self, identity: Any) -> None:
        if not self.can_edit(identity):
            raise RingSetupError("RING_OWNER_REQUIRED")

    def status(self, identity: Any) -> dict[str, Any]:
        can_edit = self.can_edit(identity)
        connection = getattr(self.adapter, "connection", None)
        online = bool(connection and connection.connected)
        rows = self.adapter.provider_inventory() if self.adapter is not None else []
        ring = [
            r
            for r in rows
            if r.get("present")
            and r.get("external_object_kind") == "entity"
            and r.get("metadata", {}).get("platform") == "ring"
        ]
        count = sum(
            str(r.get("external_id", "")).startswith("event.")
            and not r.get("metadata", {}).get("disabled_by")
            for r in ring
        )
        configured = bool(ring) or self._configured
        return {
            "configured": configured,
            # This is HA transport connectivity, not a claimed Ring cloud receipt.
            "connected": online and configured,
            "connection_basis": "HA_TRANSPORT",
            "state": "WAITING_HA_SETUP"
            if self.adapter is None
            else "HA_UNAVAILABLE"
            if not online
            else "CONFIGURED"
            if configured
            else "WAITING_RING_SETUP",
            "can_edit": can_edit,
            "can_setup": can_edit and online,
            "event_entities": count,
            "video_access": False,
            "event_receipt_verified": False,
        }

    def _connection(self) -> Any:
        connection = getattr(self.adapter, "connection", None)
        if connection is None or not connection.connected:
            raise RingSetupError("RING_HA_UNAVAILABLE")
        return connection

    def _project(self, setup_id: str, flow: _Flow, result: Any) -> dict[str, Any]:
        if not isinstance(result, dict):
            raise RingSetupError("RING_FLOW_UNSUPPORTED")
        if result.get("type") == "create_entry":
            self._flows.pop(setup_id, None)
            self._configured = True
            return {"status": "SUCCEEDED", "configured": True, "refresh_required": True}
        if result.get("type") == "abort":
            self._flows.pop(setup_id, None)
            reason = result.get("reason")
            return {
                "status": "ABORTED",
                "reason": "ALREADY_CONFIGURED"
                if reason == "already_configured"
                else "SETUP_ABORTED",
            }
        step = result.get("step_id")
        ha_id = result.get("flow_id")
        if (
            result.get("type") != "form"
            or step not in {"user", "2fa"}
            or not isinstance(ha_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", ha_id)
        ):
            raise RingSetupError("RING_FLOW_UNSUPPORTED")
        if flow.ha_id and flow.ha_id != ha_id:
            raise RingSetupError("RING_FLOW_UNSUPPORTED")
        flow.ha_id, flow.step = ha_id, step
        self._flows[setup_id] = flow
        errors = result.get("errors")
        error = errors.get("base") if isinstance(errors, dict) else None
        return {
            "status": "FORM",
            "setup_id": setup_id,
            "step_id": step,
            "fields": [
                {
                    "name": name,
                    "type": "text" if name == "username" else "password",
                    "required": True,
                }
                for name in (("username", "password") if step == "user" else ("2fa",))
            ],
            "errors": {"base": "INVALID_AUTH" if error == "invalid_auth" else "SETUP_FAILED"}
            if error
            else {},
        }

    def start(self, identity: Any) -> dict[str, Any]:
        self.require_owner(identity)
        with self._lock:
            now = time.monotonic()
            self._flows = {key: flow for key, flow in self._flows.items() if flow.expires > now}
            if len(self._flows) >= 8:
                raise RingSetupError("RING_FLOW_LIMIT")
            connection = self._connection()
            flow = _Flow(identity.principal_id, connection, "", "", now + 600)
            setup_id = str(uuid4())
            try:
                return self._project(setup_id, flow, connection.start_config_flow("ring"))
            except RingSetupError:
                raise
            except Exception:
                raise RingSetupError("RING_HA_UNAVAILABLE") from None

    def continue_setup(self, identity: Any, setup_id: str, user_input: Any) -> dict[str, Any]:
        self.require_owner(identity)
        with self._lock:
            flow = self._flows.get(setup_id)
            if (
                flow is None
                or flow.principal_id != identity.principal_id
                or flow.expires <= time.monotonic()
                or flow.connection is not self._connection()
            ):
                raise RingSetupError("RING_FLOW_EXPIRED")
            fields = {"username", "password"} if flow.step == "user" else {"2fa"}
            if not isinstance(user_input, dict) or set(user_input) != fields:
                raise RingSetupError("RING_INVALID_FIELDS")
            for name, value in user_input.items():
                maximum = 1024 if name == "password" else 254 if name == "username" else 32
                if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                    raise RingSetupError("RING_INVALID_FIELDS")
            # Consume before network call; ambiguous failure must not replay credentials.
            self._flows.pop(setup_id)
            try:
                result = flow.connection.continue_ring_config_flow(flow.ha_id, user_input)
                return self._project(setup_id, flow, result)
            except RingSetupError:
                raise
            except Exception:
                raise RingSetupError("RING_HA_UNAVAILABLE") from None
