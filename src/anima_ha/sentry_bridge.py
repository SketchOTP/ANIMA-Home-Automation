"""Long-running ANIMA-side Attention pump for the SENTRY integration.

This process does not execute Home Assistant calls.  It advances the durable
Attention cursor and creates fenced SENTRY requests.  SENTRY claims those
requests through ``anima-sentry-mcp`` and returns structured results through
the same Core boundary.
"""

from __future__ import annotations

import argparse
import os
import time
from uuid import UUID

from anima_ha.attention import default_attention_profile
from anima_ha.db.migrate import migrate
from anima_ha.intelligence import SentryAttentionBridge
from anima_ha.ui_runtime import build_postgres_core


def main() -> int:
    parser = argparse.ArgumentParser(description="Pump ANIMA Attention into SENTRY")
    parser.add_argument("--once", action="store_true", help="process one Attention cycle")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--consumer-name", default="sentry-attention")
    args = parser.parse_args()
    if args.interval <= 0 or args.interval > 60:
        parser.error("--interval must be between 0 and 60 seconds")
    if not args.consumer_name.strip() or len(args.consumer_name) > 128:
        parser.error("--consumer-name must be 1-128 characters")
    database_url = os.environ.get("ANIMA_DATABASE_URL", "").strip()
    household_value = os.environ.get("ANIMA_HOUSEHOLD_ID", "").strip()
    if not database_url or not household_value:
        parser.error("ANIMA_DATABASE_URL and ANIMA_HOUSEHOLD_ID are required")
    household_id = UUID(household_value)
    migrate(database_url, 5)
    core = build_postgres_core(database_url)
    if core.intelligence_store is None:
        raise SystemExit("ANIMA intelligence store is unavailable")
    bridge = SentryAttentionBridge(
        attention=core.attention,
        context=core.context,
        store=core.intelligence_store,
        profile=default_attention_profile("phase13.sentry.v1"),
    )
    while True:
        bridge.run_once(
            household_id=household_id,
            tools=core.plugins.list_tools(),
            consumer_name=args.consumer_name,
        )
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
