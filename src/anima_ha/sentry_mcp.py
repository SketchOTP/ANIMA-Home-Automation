"""Retired in-process SENTRY transport.

SENTRY must use ``integrations/sentry/anima-household`` as a client of the
ANIMA-owned ``anima-core-service``. This module remains only as a migration
guard so an old command cannot accidentally start ANIMA Core inside SENTRY.
"""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Retired: launch anima-core-service separately and install anima-household"
    )
    parser.error("the in-process SENTRY MCP is retired; use the remote anima-household client")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
