"""Authenticated presentation of owner-bound, coarse household presence."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from anima_ha.graph import NodeKind


class PresenceAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: dict[str, Any]


def install_household_presence_api(
    app: FastAPI,
    service: Any,
    *,
    current_identity: Callable[..., Any],
    current_session: Callable[..., Any],
    require_mutation: Callable[..., Any],
) -> None:
    def call(identity: Any, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        operation = getattr(service.commands, "presence_operation", None)
        if not callable(operation):
            raise HTTPException(503, "HOUSEHOLD_PRESENCE_UNAVAILABLE")
        try:
            result: dict[str, Any] = operation(identity, name, payload)
            return result
        except RuntimeError:
            raise HTTPException(503, "HOUSEHOLD_PRESENCE_UNAVAILABLE") from None

    def read(identity: Any, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = call(identity, name, payload)
        if result.get("status") != "SUCCEEDED":
            denied = result.get("status") in {"DENIED", "REQUIRE_STRONGER_AUTH"}
            raise HTTPException(403 if denied else 503, "HOUSEHOLD_PRESENCE_READ_UNAVAILABLE")
        data = result.get("result")
        if not isinstance(data, dict):
            raise HTTPException(503, "HOUSEHOLD_PRESENCE_READ_UNAVAILABLE")
        return data

    @app.get("/api/v1/presence")
    def presence(
        request: Request,
        limit: int = Query(default=20, ge=1, le=50),
        cursor: str | None = None,
        person_id: str | None = None,
    ) -> dict[str, Any]:
        identity = current_identity(request)
        payload: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            payload["cursor"] = cursor
        if person_id is not None:
            payload["person_id"] = person_id
        data = read(identity, "snapshot", payload)
        graph = getattr(service.read_model, "graph", None)
        members = (
            [
                {"person_id": str(item.canonical_id), "name": item.name}
                for item in graph.members_of_household(identity.household_id)
                if item.kind == NodeKind.PERSON and item.retired_at is None
            ]
            if graph
            else []
        )
        person = graph.get_node(identity.principal_id) if graph else None
        return {
            **data,
            "members": members,
            "can_edit": bool(
                person
                and person.retired_at is None
                and person.metadata.get("semantic_role") == "owner"
            ),
        }

    @app.get("/api/v1/presence/sources")
    def sources(
        request: Request,
        limit: int = Query(default=20, ge=1, le=50),
        cursor: str | None = None,
    ) -> dict[str, Any]:
        identity = current_identity(request)
        payload: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            payload["cursor"] = cursor
        result = read(identity, "list_sources", payload)
        # Only an authenticated owner UI gets canonical display names. Network
        # identifiers and coordinates never enter the model-facing source list.
        graph = getattr(service.read_model, "graph", None)
        if graph:
            from uuid import UUID

            for item in result.get("items", []):
                resource = graph.get_node(UUID(item["resource_id"]))
                item["name"] = resource.name if resource else "Phone presence source"
        return result

    @app.post("/api/v1/presence/bind")
    def bind(
        request: Request,
        body: PresenceAssignment,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        return call(service.identity_from_session(session), "bind_source", body.payload)
