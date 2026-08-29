"""Development simulator entrypoint; event semantics are intentionally deferred."""

from __future__ import annotations

import argparse
import logging
import time

from anima_ha.config import RuntimeConfig
from anima_ha.logging_setup import configure_logging

LOGGER = logging.getLogger("anima_ha.simulator")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ANIMA HA development simulator framework")
    parser.add_argument(
        "--once",
        action="store_true",
        help="report readiness and exit; no simulated household event is emitted",
    )
    parser.add_argument("--duration", type=float, default=0.0, help="optional readiness duration")
    return parser


def run(*, once: bool = False, duration: float = 0.0) -> int:
    config = RuntimeConfig.from_environment()
    configure_logging(config.log_level)
    LOGGER.info(
        "simulator_ready",
        extra={"mode": "framework-only", "event_semantics": "deferred"},
    )
    if not once and duration > 0:
        time.sleep(duration)
    LOGGER.info("simulator_stopped", extra={"reason": "baseline_exit"})
    return 0


def main() -> int:
    args = build_parser().parse_args()
    return run(once=args.once, duration=args.duration)


if __name__ == "__main__":
    raise SystemExit(main())
