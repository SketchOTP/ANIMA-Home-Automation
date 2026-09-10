"""Authenticated knowledge HTTP projection; all tools still pass Core policy."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from anima_ha.ui_api import SessionRecord, UIIdentity, UIService


class KnowledgeMutationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: dict[str, Any]


def install_knowledge_api(
    app: FastAPI,
    service: UIService,
    current_identity: Callable[[Request], UIIdentity],
    current_session: Callable[[Request], SessionRecord],
    require_mutation: Callable[[Request, str | None, SessionRecord], None],
) -> None:
    from anima_ha.ui_api import UICommandError

    def operation(identity: UIIdentity, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        command = getattr(service.commands, "knowledge_operation", None)
        if not callable(command):
            raise HTTPException(503, "KNOWLEDGE_NOT_CONFIGURED")
        try:
            result: dict[str, Any] = command(identity, name, payload)
        except UICommandError:
            raise HTTPException(503, "KNOWLEDGE_UNAVAILABLE") from None
        return result

    def read(identity: UIIdentity, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = operation(identity, name, payload)
        if result.get("status") != "SUCCEEDED":
            if result.get("reason") == "KnowledgeConflict":
                raise HTTPException(409, "KNOWLEDGE_EDIT_CONFLICT")
            denied = result.get("status") in {"DENIED", "REQUIRE_STRONGER_AUTH"}
            raise HTTPException(
                403 if denied else 503,
                "KNOWLEDGE_READ_DENIED" if denied else "KNOWLEDGE_READ_UNAVAILABLE",
            )
        data = result.get("result")
        if not isinstance(data, dict):
            raise HTTPException(503, "KNOWLEDGE_READ_UNAVAILABLE")
        return data

    @app.get("/api/v1/knowledge-status")
    def status(request: Request) -> dict[str, Any]:
        current_identity(request)
        manager = getattr(service.commands, "manager", None)
        tools = manager.list_tools() if manager is not None else []
        available = any(
            tool.tool_id == "anima.knowledge.search_notes" and tool.availability for tool in tools
        )
        agent_memory_enabled = os.environ.get("ANIMA_SENTRY_AGENT_MEMORY", "").lower() == "true"
        return {
            "available": available,
            "agent_memory_enabled": agent_memory_enabled,
            "storage": "OBSIDIAN_MANAGED_MARKDOWN",
            "scope": "HOUSEHOLD",
            "authority": "NONE",
            "automatic_capture": "DECISION_SUMMARIES_AND_MODEL_SELECTED_NOTES",
            "decision_journal": (
                "ENABLED_FOR_ELIGIBLE_TURNS"
                if available and agent_memory_enabled
                else "NOT_ENABLED"
            ),
            "writer_status": "CONFIGURED"
            if available and agent_memory_enabled
            else "NOT_CONFIGURED",
        }

    @app.get("/api/v1/knowledge-search")
    def search(
        request: Request,
        query: str = Query(default="", max_length=120),
        person_id: str | None = None,
        note_type: str | None = None,
        limit: int = Query(default=10, ge=1, le=20),
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": query, "limit": limit}
        if person_id is not None:
            payload["person_id"] = person_id
        if note_type is not None:
            payload["note_type"] = note_type
        return read(current_identity(request), "search_notes", payload)

    @app.get("/api/v1/knowledge-index")
    def index(request: Request, cursor: str | None = None) -> dict[str, Any]:
        return read(current_identity(request), "memory_index", {"limit": 50, "cursor": cursor})

    @app.get("/api/v1/knowledge")
    def notes(
        request: Request,
        limit: int = Query(default=50, ge=1, le=50),
        cursor: str | None = None,
        query: str = Query(default="", max_length=120),
        include_inactive: bool = False,
    ) -> dict[str, Any]:
        return read(
            current_identity(request),
            "list_notes",
            {
                "limit": limit,
                "cursor": cursor,
                "query": query,
                "include_inactive": include_inactive,
            },
        )

    @app.get("/api/v1/knowledge/{note_id}")
    def note(note_id: str, request: Request) -> dict[str, Any]:
        return read(current_identity(request), "get_note", {"note_id": note_id})

    @app.post("/api/v1/knowledge/{action}")
    def mutate(
        action: str,
        request: Request,
        body: KnowledgeMutationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        names = {
            "create": "create_note",
            "update": "update_note",
            "retract": "retract_note",
            "purge-expired": "purge_expired",
        }
        if action not in names:
            raise HTTPException(404, "UNKNOWN_KNOWLEDGE_OPERATION")
        return operation(service.identity_from_session(session), names[action], body.payload)
