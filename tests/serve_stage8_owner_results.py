"""Guarded mounted owner-result qualification; real Core/PG/OPA, scripted model.

Uses the existing worker/client and an intentionally delayed ephemeral publisher.
No installed credentials, provider, speaker or owner database is consulted.
"""

from __future__ import annotations

import importlib
import os
import signal
import sys
import tempfile
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

import psycopg
import pytest
import uvicorn
from test_stage3_household_situation import situation
from test_stage6_owner_postgres import connected

from anima_ha.db.migrate import migrate
from anima_ha.live_results import PostgresSentryLivePublisher, PostgresSentryLiveResultBus
from anima_ha.sentry_service import (
    CoreSentryHTTPService,
    SentryServicePrincipal,
    _Handler,
    _UnixHTTPServer,
)
from anima_ha.ui_api import create_app


def main() -> None:
    url = os.environ["ANIMA_STAGE2_TEST_DATABASE_URL"]
    with psycopg.connect(url) as conn:
        assert conn.execute("SELECT current_database(),current_user").fetchone() == (
            "anima_vendor_ingress_test",
            "stage2",
        )
        assert conn.execute(
            "SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user"
        ).fetchone() == (False, False, False)
    assert os.environ["ANIMA_STAGE3_TEST_OPA_URL"].startswith("http://127.0.0.1:")
    for key in ("SENTRY_AUTHORITY_ROOT", "SENTRY_AGENT_WORKSPACE", "CODEX_HOME", "XDG_STATE_HOME"):
        assert os.environ[key].startswith("/tmp/")
    os.environ["ANIMA_INTELLIGENCE_PROVIDER"] = "sentry"
    assert (
        Path(str(__import__("anima_ha").__file__))
        .resolve()
        .is_relative_to(Path(__file__).resolve().parents[1] / "src")
    )
    migrate(url, 5)

    def terminate(signum: int, frame: object) -> None:
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, terminate)
    household = situation.__wrapped__(url)  # type: ignore[attr-defined]
    value = next(household)
    try:
        with tempfile.TemporaryDirectory(prefix="anima-stage8-browser-") as directory:
            with pytest.MonkeyPatch.context() as patch:
                root = Path(directory)
                fixture = connected.__wrapped__(value, patch, root)  # type: ignore[attr-defined]
                data = next(fixture)
                ui, core = data["service"], data["service"].core_runtime
                core.graph.update_person_profile(
                    data["home"], data["owner"], access_level="UNRESTRICTED"
                )
                plugin = core.plugins.plugins["anima.provider.home-assistant"]
                tool = next(t for t in plugin.tools.values() if t.name == "set_power")
                tool = replace(tool, risk_class="EXTERNAL_SIDE_EFFECT")
                plugin.tools[tool.tool_id] = core.plugins.tools[tool.tool_id] = tool
                integration = (
                    Path(__file__).resolve().parents[1] / "integrations/sentry/anima-household"
                )
                sys.path.insert(0, str(integration))
                AnimaHouseholdClient = importlib.import_module(
                    "anima_household_client"
                ).AnimaHouseholdClient
                HouseholdWorker = importlib.import_module("household_worker").HouseholdWorker

                stats = {"plan": 0, "final": 0, "published": 0}
                published_by_request: dict[str, int] = {}
                stop = threading.Event()
                publisher = PostgresSentryLivePublisher(url)

                class DelayedPublisher:
                    def publish(self, payload: dict[str, Any]) -> None:
                        # Terminal store metadata is already committed. Delay
                        # only the actual live notification, not the provider.
                        if not stop.wait(3):
                            publisher.publish(payload)
                            stats["published"] += 1
                            request_id = str(payload["request_id"])
                            published_by_request[request_id] = (
                                published_by_request.get(request_id, 0) + 1
                            )

                token = "stage8-synthetic-browser-worker-credential-only"
                credential = root / "credential"
                credential.write_text(token)
                credential.chmod(0o600)
                service = CoreSentryHTTPService(
                    core.sentry_boundary(),
                    lambda: token,
                    service_principal=SentryServicePrincipal.from_secret(
                        client_id="stage8-browser-worker",
                        household_id=data["home"],
                        provider_id="sentry",
                        token=token,
                    ),
                    live_result_publisher=DelayedPublisher(),  # type: ignore[arg-type]
                )
                server = _UnixHTTPServer(str(root / "core.sock"), _Handler)
                server.service = service
                server_thread = threading.Thread(target=server.serve_forever, daemon=True)
                server_thread.start()
                client = AnimaHouseholdClient(str(root / "core.sock"), str(credential))
                bus = PostgresSentryLiveResultBus(url)
                ui.sentry_results = bus

                class ScriptedModel:
                    heartbeat: Any = None

                    def check_auth(self) -> bool:
                        return True

                    def plan(self, context: Any, catalogue: Any) -> dict[str, Any]:
                        stats["plan"] += 1
                        self.heartbeat()
                        if not any(item["tool_id"] == tool.tool_id for item in catalogue) or (
                            stats["plan"] % 3 == 2
                        ):
                            return {"calls": []}
                        return {
                            "calls": [
                                {
                                    "tool_id": tool.tool_id,
                                    "arguments": {
                                        "resource_id": str(data["resources"][0]),
                                        "desired_on": data["transport"].values[
                                            "input_boolean.stage6_a"
                                        ]
                                        != "on",
                                        "capability_id": str(
                                            core.graph.resource_capabilities(data["resources"][0])[
                                                0
                                            ].canonical_id
                                        ),
                                    },
                                }
                            ]
                        }

                    def final(self, context: Any, results: Any) -> str:
                        stats["final"] += 1
                        self.heartbeat()
                        return "Synthetic current saved task result, no spoken delivery claimed."

                worker = HouseholdWorker(client, ScriptedModel(), stop=stop)
                errors: list[str] = []

                def consume() -> None:
                    while not stop.is_set():
                        try:
                            core.owner_task_results.run_once()
                            worker.run_once()
                        except Exception as exc:
                            errors.append(type(exc).__name__)
                        stop.wait(0.2)

                worker_thread = threading.Thread(target=consume, daemon=True)
                worker_thread.start()
                app = create_app(ui)

                @app.get("/stage8-fixture-evidence")
                def evidence() -> dict[str, Any]:
                    return {
                        **stats,
                        "published_by_request": dict(published_by_request),
                        "errors": errors,
                        "physical_calls": len(data["transport"].calls),
                    }

                # Test-only readback precedes the existing catch-all UI mount.
                app.router.routes.insert(0, app.router.routes.pop())
                try:
                    uvicorn.run(app, host="127.0.0.1", port=18338, log_level="warning")
                finally:
                    stop.set()
                    worker_thread.join(timeout=10)
                    assert not worker_thread.is_alive()
                    server.shutdown()
                    server.server_close()
                    server_thread.join(timeout=3)
                    ui.sentry_results = None
                    bus.close()
                    fixture.close()
    finally:
        household.close()


if __name__ == "__main__":
    main()
