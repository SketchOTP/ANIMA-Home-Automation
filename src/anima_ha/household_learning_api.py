"""Owner presentation for household learning; model cannot edit delivery settings."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict


class LearningMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: dict[str, Any]


def install_household_learning_api(
    app: FastAPI,
    service: Any,
    *,
    current_identity: Callable[..., Any],
    current_session: Callable[..., Any],
    require_mutation: Callable[..., Any],
) -> None:
    def learning() -> Any:
        result = getattr(getattr(service, "core_runtime", None), "learning_service", None)
        if result is None:
            raise HTTPException(503, "HOUSEHOLD_LEARNING_UNAVAILABLE")
        return result

    @app.get("/api/v1/initiative")
    def status(request: Request) -> dict[str, Any]:
        identity = current_identity(request)
        manager = learning()
        try:
            result: dict[str, Any] = manager.status(identity.household_id)
            person = manager.graph.get_node(identity.principal_id)
            can_edit = bool(
                person
                and person.retired_at is None
                and person.metadata.get("semantic_role") == "owner"
                and any(
                    n.canonical_id == identity.principal_id
                    for n in manager.graph.members_of_household(identity.household_id)
                )
            )
            return {
                **result,
                "can_edit": can_edit,
                "running_status": "AWAITING_SENTRY_CONSUMER"
                if os.environ.get("ANIMA_SENTRY_AUTOWAKE_ENABLED_AT", "").strip()
                else "AUTO_WAKE_DISABLED",
            }
        except Exception:
            raise HTTPException(503, "HOUSEHOLD_LEARNING_UNAVAILABLE") from None

    @app.get("/api/v1/initiative/suggestions")
    def suggestions(request: Request, limit: int = 20, cursor: str | None = None) -> dict[str, Any]:
        identity = current_identity(request)
        try:
            result: dict[str, Any] = learning().suggestions(
                identity.household_id, limit=limit, cursor=cursor
            )
            return result
        except ValueError:
            raise HTTPException(400, "INVALID_LEARNING_PAGE") from None

    @app.post("/api/v1/initiative/{operation}")
    def mutate(
        operation: str,
        request: Request,
        body: LearningMutation,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        if operation not in {"configure", "review"}:
            raise HTTPException(404, "UNKNOWN_LEARNING_OPERATION")
        invoke = getattr(service.commands, "learning_operation", None)
        if not callable(invoke):
            raise HTTPException(503, "HOUSEHOLD_LEARNING_UNAVAILABLE")
        try:
            result: dict[str, Any] = invoke(
                service.identity_from_session(session), operation, body.payload
            )
            return result
        except (ValueError, TypeError):
            raise HTTPException(400, "INVALID_LEARNING_INPUT") from None
        except RuntimeError:
            raise HTTPException(503, "HOUSEHOLD_LEARNING_UNAVAILABLE") from None
