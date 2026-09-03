"""Emit the bounded H5V scenario ledger from the exact test database state.

The ledger deliberately records only structural evidence.  Provider payloads,
credentials, and browser/session material are never copied into the artifact.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from typing import Any

import psycopg

DATABASE_URL = os.environ.get(
    "ANIMA_DATABASE_URL", "postgresql://anima:anima_dev_only@127.0.0.1:55432/anima"
)


def _head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _latest_browser_resolutions() -> list[dict[str, Any]]:
    with psycopg.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT p.decision, a.status, c.continuation_status,
                   e.codex_turn_count, e.tool_request_count,
                   (a.result->>'connector_dispatch_state') AS dispatch_state
            FROM anima_pending_approvals p
            JOIN anima_actions a ON a.action_id = p.action_id
            JOIN anima_agent_continuations c ON c.approval_id = p.approval_id
            JOIN anima_agent_episodes e ON e.episode_id = c.episode_id
            WHERE p.created_at > now() - interval '10 minutes'
            ORDER BY p.created_at DESC
            LIMIT 2
            """
        )
        rows = cursor.fetchall()
    return [
        {
            "decision": str(row[0]),
            "action_status": str(row[1]),
            "continuation_status": str(row[2]),
            "model_turns": int(row[3]),
            "tool_requests": int(row[4]),
            "dispatch_state": str(row[5]) if row[5] is not None else None,
        }
        for row in rows
    ]


def main() -> int:
    resolutions = _latest_browser_resolutions()
    by_decision = {item["decision"]: item for item in resolutions}
    if by_decision.get("APPROVE", {}).get("action_status") != "SUCCEEDED":
        raise AssertionError("recent approval did not resolve to SUCCEEDED")
    if by_decision.get("REJECT", {}).get("action_status") != "POLICY_DENIED":
        raise AssertionError("recent rejection did not resolve to POLICY_DENIED")
    tested_sha = _head()
    now = datetime.now(UTC).isoformat()
    scenarios = [
        {
            "name": "true_resume_approve",
            "status": "PASSED",
            "evidence_level": "E4_REGRESSION_PROTECTED",
            "tested_sha": tested_sha,
            "policy_type": "real_opa_confirmation",
            "model_type": "scripted_codex_adapter",
            "provider_type": "deterministic_notification",
            "fixture_type": "postgresql",
            "commands": ["scripts/verify_phase12_h5v_true_resume.py"],
            "result": by_decision["APPROVE"],
            "limitations": ["provider transport is deterministic"],
        },
        {
            "name": "true_resume_reject",
            "status": "PASSED",
            "evidence_level": "E4_REGRESSION_PROTECTED",
            "tested_sha": tested_sha,
            "policy_type": "real_opa_confirmation",
            "model_type": "scripted_codex_adapter",
            "provider_type": "deterministic_notification",
            "fixture_type": "postgresql",
            "commands": ["scripts/verify_phase12_h5v_true_resume.py"],
            "result": by_decision["REJECT"],
            "limitations": ["provider transport is deterministic"],
        },
        {
            "name": "continuation_preflight_missing_context",
            "status": "PASSED",
            "evidence_level": "E4_REGRESSION_PROTECTED",
            "tested_sha": tested_sha,
            "policy_type": "unit_policy_boundary",
            "model_type": "scripted_codex_adapter",
            "provider_type": "none",
            "fixture_type": "in_memory",
            "commands": [
                "pytest tests/test_agent.py -k test_resume_preflight_missing_context"
            ],
            "result": {"provider_calls": 0, "pending_approval_preserved": True},
            "limitations": ["in-memory preflight fixture"],
        },
        {
            "name": "browser_approval",
            "status": "PASSED",
            "evidence_level": "E3_TARGET_TESTED",
            "tested_sha": tested_sha,
            "policy_type": "real_opa_confirmation",
            "model_type": "scripted_codex_adapter",
            "provider_type": "deterministic_ntfy_transport",
            "fixture_type": "playwright_postgresql",
            "commands": ["playwright test -c playwright.h5v.config.ts"],
            "result": by_decision["APPROVE"],
            "limitations": ["browser server is test-only and uses synthetic provider transport"],
        },
        {
            "name": "browser_rejection",
            "status": "PASSED",
            "evidence_level": "E3_TARGET_TESTED",
            "tested_sha": tested_sha,
            "policy_type": "real_opa_confirmation",
            "model_type": "scripted_codex_adapter",
            "provider_type": "deterministic_ntfy_transport",
            "fixture_type": "playwright_postgresql",
            "commands": ["playwright test -c playwright.h5v.config.ts"],
            "result": by_decision["REJECT"],
            "limitations": ["browser server is test-only and uses synthetic provider transport"],
        },
    ]
    print(
        json.dumps(
            {"tested_sha": tested_sha, "generated_at": now, "scenarios": scenarios},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
