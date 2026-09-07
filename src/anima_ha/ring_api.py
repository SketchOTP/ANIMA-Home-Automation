"""Credential-bearing owner UI endpoint. Never expose it as a model tool."""

from __future__ import annotations

import json
from collections.abc import Callable
from threading import Lock
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from anima_ha.ring_setup import RingSetupError, RingSetupService


def install_ring_api(
    app: FastAPI,
    service: Any,
    *,
    current_identity: Callable[..., Any],
    current_session: Callable[..., Any],
    require_mutation: Callable[..., Any],
) -> None:
    cache: dict[str, Any] = {}
    lock = Lock()

    def setup(identity: Any) -> RingSetupService:
        core = service.core_runtime
        adapter = getattr(core, "home_assistant_adapter", None)
        key = (id(core), id(adapter), identity.household_id)
        with lock:
            if cache.get("key") != key:
                cache.clear()
                cache.update(key=key, value=RingSetupService(adapter, identity.household_id))
            value: RingSetupService = cache["value"]
            return value

    @app.get("/api/v1/ring/status")
    def status(request: Request) -> dict[str, Any]:
        identity = current_identity(request)
        return setup(identity).status(identity)

    @app.post("/api/v1/ring/setup/{operation}")
    async def configure(
        operation: str,
        request: Request,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        identity = service.identity_from_session(session)
        manager = setup(identity)
        try:
            await run_in_threadpool(manager.require_owner, identity)
        except RingSetupError:
            raise HTTPException(403, "RING_OWNER_REQUIRED") from None
        if operation not in {"start", "continue"}:
            raise HTTPException(404, "NOT_FOUND")
        # Auth/owner/CSRF before parsing. No Pydantic error can echo a password.
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > 4096:
                raise HTTPException(413, "RING_INPUT_TOO_LARGE")
            raw.extend(chunk)
        try:
            body = json.loads(raw or b"{}")
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(400, "RING_INVALID_FIELDS") from None
        finally:
            raw.clear()
        try:
            if not isinstance(body, dict):
                raise RingSetupError("RING_INVALID_FIELDS")
            if operation == "start":
                if body:
                    raise RingSetupError("RING_INVALID_FIELDS")
                return await run_in_threadpool(manager.start, identity)
            if set(body) != {"setup_id", "user_input"} or not isinstance(body["setup_id"], str):
                raise RingSetupError("RING_INVALID_FIELDS")
            return await run_in_threadpool(
                manager.continue_setup, identity, body["setup_id"], body["user_input"]
            )
        except RingSetupError as exc:
            raise HTTPException(
                403 if str(exc) == "RING_OWNER_REQUIRED" else 400, str(exc)
            ) from None
