"""Real child composition in the explicitly isolated disposable test store."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from anima_ha.db.migrate import migrate
from anima_ha.graph import CanonicalNode, CommissioningDocument, NodeKind, PostgresHouseholdGraph

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def isolated_bridge_url() -> Iterator[str]:
    url = os.environ.get("ANIMA_STAGE3_BRIDGE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("requires explicit isolated bridge review database")
    with psycopg.connect(url) as connection:
        assert connection.execute("SELECT current_database(),current_user").fetchone() == (
            "anima_stage3_bridge_review",
            "stage2",
        )
    # Prior runs leave immutable triggers in the shared review database. The
    # global Attention profile deliberately enumerates those too, so isolate
    # this positive/negative child fixture without deleting their evidence.
    database = f"anima_stage3_bridge_fixture_{uuid4().hex}"
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(
            sql.SQL("CREATE DATABASE {} OWNER stage2").format(sql.Identifier(database))
        )
    fixture_url = make_conninfo(url, dbname=database)
    try:
        with psycopg.connect(fixture_url) as connection:
            assert connection.execute("SELECT current_database(),current_user").fetchone() == (
                database,
                "stage2",
            )
        migrate(fixture_url, 5)
        yield fixture_url
    finally:
        with psycopg.connect(url, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


def child_environment(url: str) -> dict[str, str]:
    # Do not inherit a host credential file, adapter or service binding into a
    # child fixture. These tests have no owner-store or network authorization.
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("ANIMA_", "HA_", "SENTRY_"))
    }
    environment.update(
        ANIMA_DATABASE_URL=url,
        PYTHONPATH=str(ROOT / "src"),
        PYTHONDONTWRITEBYTECODE="1",
    )
    return environment


@pytest.mark.parametrize("scope", ["missing", "wrong_kind", "retired"])
def test_child_rejects_uncommissioned_scope(isolated_bridge_url: str, scope: str) -> None:
    household_id = uuid4()
    graph = PostgresHouseholdGraph(isolated_bridge_url)
    if scope != "missing":
        graph.commission(
            CommissioningDocument(
                version=1,
                nodes=(CanonicalNode(household_id, NodeKind.HOUSEHOLD, "Negative fixture"),),
            )
        )
        with psycopg.connect(isolated_bridge_url) as connection:
            if scope == "wrong_kind":
                connection.execute(
                    "UPDATE anima_graph_nodes SET kind='ROOM' WHERE canonical_id=%s",
                    (household_id,),
                )
            else:
                connection.execute(
                    "UPDATE anima_graph_nodes SET retired_at=now() WHERE canonical_id=%s",
                    (household_id,),
                )
    environment = child_environment(isolated_bridge_url)
    environment["ANIMA_HOUSEHOLD_ID"] = str(household_id)
    child = subprocess.run(
        [
            "timeout",
            "--kill-after=2s",
            "20s",
            sys.executable,
            "-m",
            "anima_ha.sentry_bridge",
            "--once",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert child.returncode != 0
    assert "Canonical handoff requires an active commissioned household" in child.stderr
    with psycopg.connect(isolated_bridge_url) as connection:
        assert connection.execute(
            "SELECT count(*) FROM anima_intelligence_requests WHERE household_id=%s",
            (household_id,),
        ).fetchone() == (0,)


def test_bridge_fixture_commissions_before_both_children_and_retains_idempotency(
    isolated_bridge_url: str,
) -> None:
    child = subprocess.run(
        [
            "timeout",
            "--kill-after=2s",
            # Each actual Core startup appends lifecycle Journal events. The
            # normal guaranteed Attention profile processes those as well as
            # our one user event; both complete child cycles are bounded here.
            "120s",
            sys.executable,
            str(ROOT / "scripts/verify_phase14_sentry_bridge_restart_r2.py"),
        ],
        cwd=ROOT,
        env=child_environment(isolated_bridge_url),
        capture_output=True,
        text=True,
        check=True,
        timeout=130,
    )
    result = json.loads(child.stdout)
    assert result["status"] == "PASS"
    assert result["request_count_before_restart"] == result["request_count_after_restart"] == 1
    assert result["embedded_agent_runtime"] is False
    observations = result["process_observations"]
    assert len(observations) == 2
    assert all(item["elapsed_seconds"] > 0 for item in observations)
    assert all(item["plugin_lifecycle_events_added"] > 0 for item in observations)
    assert observations[1]["trigger_count_before"] == observations[0]["trigger_count_after"]
    print(json.dumps(result, sort_keys=True))
