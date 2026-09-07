"""Authenticated HTTP presentation of the existing routine Core boundary."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from anima_ha.family_routines import (
    FamilyRoutineError,
    family_routine_options,
    family_routines_page,
)


class RoutineMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: dict[str, Any]


def install_family_routines_api(
    app: FastAPI,
    service: Any,
    *,
    current_identity: Callable[..., Any],
    current_session: Callable[..., Any],
    require_mutation: Callable[..., Any],
) -> None:
    @app.get("/api/v1/family-routines")
    def routines(
        request: Request, limit: int = 50, cursor: str | None = None, person_id: str | None = None
    ) -> dict[str, Any]:
        identity = current_identity(request)
        memory = getattr(service.read_model, "memory_service", None)
        graph = getattr(service.read_model, "graph", None)
        if memory is None or graph is None:
            raise HTTPException(503, "FAMILY_ROUTINES_UNAVAILABLE")
        try:
            page = family_routines_page(
                memory,
                graph,
                identity.household_id,
                limit=limit,
                cursor=cursor,
                person_id=person_id,
            )
            person = graph.get_node(identity.principal_id)
            return {
                **page,
                **family_routine_options(graph, identity.household_id),
                "can_edit": bool(
                    person
                    and person.retired_at is None
                    and person.metadata.get("semantic_role") == "owner"
                ),
            }
        except FamilyRoutineError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/v1/family-routines/{operation}")
    def change_routine(
        operation: str,
        request: Request,
        body: RoutineMutation,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        if operation not in {"create", "update", "disable", "retract", "add-member"}:
            raise HTTPException(404, "UNKNOWN_ROUTINE_OPERATION")
        mutation = getattr(service.commands, "family_routine_mutation", None)
        if not callable(mutation):
            raise HTTPException(503, "FAMILY_ROUTINES_UNAVAILABLE")
        try:
            result: dict[str, Any] = mutation(
                service.identity_from_session(session), operation, body.payload
            )
            return result
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, "INVALID_FAMILY_ROUTINE") from exc
        except RuntimeError as exc:
            raise HTTPException(503, "FAMILY_ROUTINES_UNAVAILABLE") from exc
