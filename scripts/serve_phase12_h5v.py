"""Start the H5V browser acceptance composition.

This is test-only infrastructure.  It uses the normal PostgreSQL/OPA/Core
composition and injects only deterministic model/provider seams.  Production
startup never imports this module and never enables test authentication.
"""

from __future__ import annotations

import os
from uuid import NAMESPACE_URL, uuid5

import httpx
import uvicorn

from anima_ha.agent import (
    CodexTurnResult,
    FinalDecision,
    ScriptedCodexAdapter,
    TokenUsage,
    ToolRequestDecision,
)
from anima_ha.fixtures import sample_household_document
from anima_ha.graph import PostgresHouseholdGraph, ProviderReference
from anima_ha.ui_api import create_app

HA_SCOPE = "phase12-h5v-browser"
HA_USER_ID = "test-ha-user"


NOTIFICATION_TOOL = "anima.external.notifications.send"


def _tool_turn() -> CodexTurnResult:
    return CodexTurnResult(
        ToolRequestDecision(
            NOTIFICATION_TOOL,
            {"title": "Anima H5V", "message": "Deterministic browser confirmation"},
        ),
        TokenUsage(),
        1.0,
        ("turn.completed",),
    )


def _final(text: str) -> CodexTurnResult:
    return CodexTurnResult(
        FinalDecision("ENOUGH_EVIDENCE", True, text, "h5v browser continuation"),
        TokenUsage(20, 0, 10, 0),
        1.0,
        ("turn.completed",),
    )


def _provider(request: httpx.Request) -> httpx.Response:
    if request.method != "POST" or request.url.host != "ntfy.sh":
        return httpx.Response(404, request=request, json={"error": "fixture route not found"})
    return httpx.Response(
        200,
        request=request,
        json={"id": "h5v-browser-fixture", "event": "published"},
    )


def main() -> None:
    database_url = os.environ.get(
        "ANIMA_DATABASE_URL", "postgresql://anima:anima_dev_only@127.0.0.1:55432/anima"
    )
    os.environ.setdefault("ANIMA_DATABASE_URL", database_url)
    os.environ.setdefault("ANIMA_OPA_URL", "http://127.0.0.1:18181")
    os.environ.setdefault("ANIMA_HA_PROVIDER_SCOPE", HA_SCOPE)
    os.environ.setdefault("NTFY_TOPIC", "h5v-browser-fixture")
    os.environ["ANIMA_UI_TEST_AUTH"] = "1"
    graph = PostgresHouseholdGraph(database_url)
    document = sample_household_document()
    graph.commission(document)
    person = next(node for node in document.nodes if node.name == "Alex")
    graph.map_provider_reference(
        ProviderReference(
            uuid5(NAMESPACE_URL, f"anima:{HA_SCOPE}:{HA_USER_ID}"),
            "home_assistant",
            HA_SCOPE,
            "user",
            HA_USER_ID,
            person.canonical_id,
        ),
        allow_remap=True,
    )
    model = ScriptedCodexAdapter(
        [
            _tool_turn(),
            _final("The notification was approved and completed."),
            _tool_turn(),
            _final("The notification was rejected and was not dispatched."),
        ]
    )
    app = create_app(codex=model, external_transport=httpx.MockTransport(_provider))
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("ANIMA_UI_PORT", "18091")))


if __name__ == "__main__":
    main()
