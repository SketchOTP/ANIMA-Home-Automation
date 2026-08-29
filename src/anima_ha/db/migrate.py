"""Minimal ordered SQL migration runner for runtime metadata only."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import psycopg

from anima_ha.config import RuntimeConfig
from anima_ha.logging_setup import configure_logging

LOGGER = logging.getLogger("anima_ha.db.migrate")
MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def migrate(database_url: str, connect_timeout: int) -> list[str]:
    applied: list[str] = []
    with psycopg.connect(database_url, connect_timeout=connect_timeout) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS anima_schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cursor.execute("SELECT version FROM anima_schema_migrations")
            existing = {row[0] for row in cursor.fetchall()}
            for path in migration_files():
                version = path.stem
                if version in existing:
                    continue
                cursor.execute(path.read_text(encoding="utf-8"))
                cursor.execute(
                    "INSERT INTO anima_schema_migrations (version) VALUES (%s)", (version,)
                )
                applied.append(version)
        connection.commit()
    return applied


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Apply ANIMA HA runtime migrations")


def main() -> int:
    build_parser().parse_args()
    config = RuntimeConfig.from_environment()
    configure_logging(config.log_level)
    applied = migrate(config.database_url, config.database_connect_timeout)
    LOGGER.info("migrations_complete", extra={"applied": applied, "count": len(applied)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
