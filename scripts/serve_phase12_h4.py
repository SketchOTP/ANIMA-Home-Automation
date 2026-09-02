"""Start the real H4 acceptance composition for Playwright.

This is an explicit test harness: it commissions one synthetic graph mapping,
uses real PostgreSQL/OPA/Core services, and injects only a scripted model.
Normal ``anima-ui`` startup does not import this module or enable test auth.
"""

from __future__ import annotations

import os

import uvicorn
from verify_phase12_h4_core import _app, _commission_identity

from anima_ha.graph import PostgresHouseholdGraph


def main() -> None:
    database_url = os.environ.get(
        "ANIMA_DATABASE_URL", "postgresql://anima:anima_dev_only@127.0.0.1:55432/anima"
    )
    os.environ.setdefault("ANIMA_DATABASE_URL", database_url)
    os.environ.setdefault("ANIMA_OPA_URL", "http://127.0.0.1:18181")
    os.environ["ANIMA_UI_TEST_AUTH"] = "1"
    _commission_identity(PostgresHouseholdGraph(database_url))
    app = _app()
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("ANIMA_UI_PORT", "18090")))


if __name__ == "__main__":
    main()
