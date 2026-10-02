"""Dedicated guarded Stage6 Core/PG/OPA browser fixture; never owner Core."""

import os
import signal
import tempfile
from pathlib import Path

import psycopg
import pytest
import uvicorn
from test_stage3_household_situation import situation
from test_stage6_owner_postgres import connected

from anima_ha.db.migrate import migrate
from anima_ha.ui_api import create_app


def main() -> None:
    url = os.environ["ANIMA_STAGE2_TEST_DATABASE_URL"]
    with psycopg.connect(url) as connection:
        if connection.execute("SELECT current_database(),current_user").fetchone() != (
            "anima_vendor_ingress_test",
            "stage2",
        ):
            raise RuntimeError("Explicit Stage2 disposable fixture required")
    if not os.environ.get("ANIMA_STAGE3_TEST_OPA_URL"):
        raise RuntimeError("Explicit isolated OPA endpoint required")
    migrate(url, 5)

    # Uvicorn re-raises captured signals to the original handler on shutdown.
    # Exit via Python so the fixture's finally blocks retire ONLY its nodes.
    def terminate(signum: int, frame: object) -> None:
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, terminate)
    household = situation.__wrapped__(url)  # type: ignore[attr-defined]
    value = next(household)
    try:
        with tempfile.TemporaryDirectory(prefix="anima-stage6-browser-") as directory:
            with pytest.MonkeyPatch.context() as patch:
                fixture = connected.__wrapped__(value, patch, Path(directory))  # type: ignore[attr-defined]
                connected_value = next(fixture)
                try:
                    uvicorn.run(
                        create_app(connected_value["service"]),
                        host="127.0.0.1",
                        port=18336,
                        log_level="warning",
                    )
                finally:
                    fixture.close()
    finally:
        household.close()


if __name__ == "__main__":
    main()
