"""Guarded real Core/PG/currentOPA UI fixture; no owner or real model turn."""

import os
import signal
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest
import uvicorn
from test_stage3_household_situation import situation
from test_stage4_learning_postgres import finish
from test_stage6_owner_postgres import connected
from test_stage7_learning_postgres import connect_review

from anima_ha.db.migrate import migrate
from anima_ha.intelligence import IntelligenceResultStatus
from anima_ha.ui_api import create_app


def main() -> None:
    url = os.environ["ANIMA_STAGE2_TEST_DATABASE_URL"]
    with psycopg.connect(url) as connection:
        if connection.execute("SELECT current_database(),current_user").fetchone() != (
            "anima_vendor_ingress_test",
            "stage2",
        ):
            raise RuntimeError("Explicit disposable Stage2 fixture required")
    if not os.environ.get("ANIMA_STAGE3_TEST_OPA_URL"):
        raise RuntimeError("Explicit isolated OPA required")
    for key in ("SENTRY_AUTHORITY_ROOT", "SENTRY_AGENT_WORKSPACE", "CODEX_HOME", "XDG_STATE_HOME"):
        if not os.environ.get(key, "").startswith("/tmp/"):
            raise RuntimeError("Temporary model-caller isolation required")
    migrate(url, 5)

    def terminate(signum: int, frame: object) -> None:
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, terminate)
    household = situation.__wrapped__(url)  # type: ignore[attr-defined]
    value = next(household)
    try:
        with tempfile.TemporaryDirectory(prefix="anima-stage7-browser-") as directory:
            with pytest.MonkeyPatch.context() as patch:
                fixture = connected.__wrapped__(value, patch, Path(directory))  # type: ignore[attr-defined]
                data = next(fixture)
                try:
                    ui = data["service"]
                    learning_data = {**data, "service": ui.core_runtime.learning_service}
                    boundary, request, _ = connect_review(learning_data, Path(directory) / "vault")
                    finish(boundary, request, IntelligenceResultStatus.NO_ACTION)
                    learning_data["clock"]["now"] = datetime.now(UTC)
                    learning = learning_data["service"]
                    learning.reconcile_reviews(data["home"])
                    frozen = learning.evaluations(data["home"])["items"][0]
                    first = frozen["prediction"]["opportunities"][0]
                    learning_data["clock"]["now"] = datetime.fromisoformat(
                        first["end"]
                    ) + timedelta(minutes=2)
                    learning.reconcile_reviews(data["home"])
                    uvicorn.run(create_app(ui), host="127.0.0.1", port=18337, log_level="warning")
                finally:
                    fixture.close()
    finally:
        household.close()


if __name__ == "__main__":
    main()
