#!/usr/bin/env python3
"""Run isolated owner-product browser journeys against their real boundaries."""

from __future__ import annotations

import os
import re
import selectors
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "ui"
TEST_DATABASE = "anima_family_routines_test"


def _database_url(database_url: str, database: str) -> str:
    values = conninfo_to_dict(database_url)
    values["dbname"] = database
    return make_conninfo(**values)


def _reset_test_database(database_url: str) -> str:
    admin_url = _database_url(database_url, "postgres")
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (TEST_DATABASE,),
        )
        connection.execute(f'DROP DATABASE IF EXISTS "{TEST_DATABASE}"')
        connection.execute(f'CREATE DATABASE "{TEST_DATABASE}"')
    return _database_url(database_url, TEST_DATABASE)


def _wait_http(url: str, process: subprocess.Popen[str], timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"fixture exited before readiness: {output[-2000:]}")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:  # noqa: S310
                if response.status < 500:
                    return
        except Exception:
            time.sleep(0.25)
    raise TimeoutError(f"fixture did not become ready: {url}")


@contextmanager
def _fixture(command: Sequence[str], env: dict[str, str]) -> Iterator[subprocess.Popen[str]]:
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    try:
        yield process
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _playwright(config: str, *tests: str, env: dict[str, str] | None = None) -> None:
    executable = UI / "node_modules" / ".bin" / "playwright"
    if not executable.exists():
        raise RuntimeError("run npm ci in ui before owner browser qualification")
    subprocess.run(
        [str(executable), "test", "-c", config, *tests, "--reporter=line"],
        cwd=UI,
        env=env,
        check=True,
    )


def _read_fixture_port(process: subprocess.Popen[str], timeout: float = 30.0) -> int:
    if process.stdout is None:
        raise RuntimeError("knowledge fixture stdout unavailable")
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout
    output: list[str] = []
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"knowledge fixture exited: {''.join(output)[-2000:]}")
        for key, _ in selector.select(timeout=0.5):
            line = key.fileobj.readline()
            output.append(line)
            match = re.search(r"\bport=(\d+)\b", line)
            if match:
                return int(match.group(1))
    raise TimeoutError(f"knowledge fixture did not report a port: {''.join(output)[-2000:]}")


def main() -> None:
    database_url = os.environ.get(
        "ANIMA_DATABASE_URL",
        "postgresql://anima:anima_dev_only@127.0.0.1:55432/anima",
    )
    opa_url = os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181")
    base_env = os.environ.copy()
    test_url = _reset_test_database(database_url)
    fixture_env = {
        **base_env,
        "ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL": test_url,
        "ANIMA_FAMILY_ROUTINES_TEST_OPA_URL": opa_url,
    }
    with _fixture([sys.executable, "tests/serve_family_routines.py"], fixture_env) as process:
        _wait_http("http://127.0.0.1:18291/healthz", process)
        _playwright("playwright.family-routines.config.ts", "family-routines.spec.ts")

    test_url = _reset_test_database(database_url)
    fixture_env["ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL"] = test_url
    with _fixture([sys.executable, "tests/serve_household_context.py"], fixture_env) as process:
        _wait_http("http://127.0.0.1:18293/healthz", process)
        _playwright(
            "playwright.household-context.config.ts",
            "preferences.spec.ts",
            "household-presence.spec.ts",
        )
        _playwright("tests/initiative-ring/real-core.config.ts")

    with _fixture(
        [sys.executable, "tests/serve_knowledge_ui.py", str(UI / "dist")],
        base_env,
    ) as process:
        port = _read_fixture_port(process)
        knowledge_env = {**base_env, "ANIMA_KNOWLEDGE_TEST_URL": f"http://127.0.0.1:{port}"}
        _wait_http(f"http://127.0.0.1:{port}/healthz", process)
        _playwright("playwright.knowledge.config.ts", env=knowledge_env)

    print("OWNER_PRODUCT_BROWSER_QUALIFICATION_PASS")


if __name__ == "__main__":
    main()
