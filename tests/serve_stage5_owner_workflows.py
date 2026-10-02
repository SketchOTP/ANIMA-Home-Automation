"""Guarded synthetic browser fixture; no owner runtime/config/provider/model."""

import os

import psycopg
import uvicorn
from test_stage3_household_situation import situation
from test_stage5_owner_postgres import owner_service

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
    migrate(url, 5)
    # Reuse the same random, isolated household as the actual PG contract tests.
    fixture = situation.__wrapped__(url)  # type: ignore[attr-defined]
    value = next(fixture)
    try:
        uvicorn.run(
            create_app(owner_service(value)), host="127.0.0.1", port=18335, log_level="warning"
        )
    finally:
        fixture.close()


if __name__ == "__main__":
    main()
