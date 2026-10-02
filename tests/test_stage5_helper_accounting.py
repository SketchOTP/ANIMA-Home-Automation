"""Actual copied helper caller with synthetic subprocesses/mocks; no model turn."""

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations/sentry/anima-household"))
from codex_model import (  # type: ignore[import-not-found]  # noqa: E402
    FINAL_SCHEMA,
    CodexHouseholdModel,
    CodexUnavailable,
)
from household_worker import HouseholdWorker  # type: ignore[import-not-found]  # noqa: E402
from test_household_worker import (  # type: ignore[import-not-found]  # noqa: E402
    FINAL,
    ClientFixture,
)

from anima_ha.model_usage import model_call_receipt


@pytest.fixture(autouse=True)
def isolated_bindings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name, directory in (
        ("SENTRY_AUTHORITY_ROOT", "authority"),
        ("SENTRY_AGENT_WORKSPACE", "workspace"),
        ("XDG_STATE_HOME", "state"),
        ("CODEX_HOME", "codex"),
    ):
        monkeypatch.setenv(name, str(tmp_path / directory))


def stream(value: dict[str, Any], usage: Any = None) -> bytes:
    return b"\n".join(
        json.dumps(event).encode()
        for event in [
            {"type": "turn.started"},
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": json.dumps(value)},
            },
            {"type": "turn.completed", "usage": usage},
        ]
    )


def test_actual_plan_final_retains_reported_and_unknown_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = CodexHouseholdModel()
    receipts: list[dict[str, Any]] = []
    model.set_model_call_sink(lambda item: receipts.append(model_call_receipt(item)))
    replies = iter([stream({"calls": []}, {"input_tokens": 11, "output_tokens": 3}), stream(FINAL)])
    monkeypatch.setattr(model, "argv", lambda *args: ["synthetic-cli"])
    monkeypatch.setattr(model, "_capture", lambda *args: (0, next(replies), b""))
    assert model.plan({}, []) == {"calls": []}
    assert model.final({}, []) == "ok"
    assert [item["phase"] for item in receipts] == ["ATTEMPTED", "FINISHED"] * 2
    assert [item["purpose"] for item in model.model_calls] == ["PLANNER", "FINAL"]
    assert model.model_calls[0]["usage"] == {"input_tokens": 11, "output_tokens": 3}
    assert model.model_calls[1]["usage"] is None
    assert model.model_calls[1]["usage_status"] == "UNKNOWN"


@pytest.mark.parametrize(
    ("failure", "status"),
    [
        (OSError("private"), "LAUNCH_FAILED"),
        (CodexUnavailable("CODEX_TIMEOUT"), "TIMEOUT"),
        (CodexUnavailable("CODEX_PROVIDER_UNAVAILABLE"), "FAILED"),
    ],
)
def test_failed_attempt_finishes_without_content_or_retry(
    monkeypatch: pytest.MonkeyPatch, failure: Exception, status: str
) -> None:
    model = CodexHouseholdModel()
    receipts = []
    model.set_model_call_sink(lambda item: receipts.append(model_call_receipt(item)))
    monkeypatch.setattr(model, "argv", lambda *args: ["synthetic-cli"])

    def capture(*args: Any) -> Any:
        raise failure

    monkeypatch.setattr(model, "_capture", capture)
    with pytest.raises(CodexUnavailable):
        model.run("private prompt never in receipt", FINAL_SCHEMA)
    assert len(receipts) == 2 and receipts[-1]["status"] == status
    assert receipts[-1]["usage_status"] == "UNKNOWN"
    assert "private" not in json.dumps(receipts)


def test_worker_auth_idle_and_deadline_are_zero_model_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = ClientFixture()
    model = CodexHouseholdModel()
    monkeypatch.setattr(model, "check_auth", lambda: True)
    client.empty = True
    assert HouseholdWorker(client, model).run_once() == {"status": "IDLE"}
    assert model.model_calls == []
    monkeypatch.setattr(model, "check_auth", lambda: False)
    with pytest.raises(CodexUnavailable):
        HouseholdWorker(client, model).run_once()
    assert model.model_calls == []
    model.set_deadline(-1)
    with pytest.raises(CodexUnavailable):
        model.run("synthetic", FINAL_SCHEMA)
    assert model.model_calls == []


def test_worker_actual_capture_uses_authenticated_metadata_before_launch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = ClientFixture()
    client.tools = lambda *args: {"tools": []}
    receipts: list[dict[str, Any]] = []

    def renew(*args: Any, **kwargs: Any) -> dict[str, Any]:
        if "model_call" in kwargs:
            receipts.append(model_call_receipt(kwargs["model_call"]))
        return {"status": "RENEWED"}

    client.renew = renew
    model = CodexHouseholdModel()
    monkeypatch.setattr(model, "check_auth", lambda: True)

    def argv(workspace: Any, schema_path: str) -> list[str]:
        # A synthetic child emits CLI protocol records. No Codex/model/provider.
        script = "import sys,json;sys.stdin.buffer.read();" + "\n".join(
            f"print({line!r},flush=True)"
            for line in stream(
                FINAL if model._call_purpose == "FINAL" else {"calls": []},
                {"input_tokens": 7, "output_tokens": 2},
            )
            .decode()
            .splitlines()
        )
        return [sys.executable, "-c", script]

    monkeypatch.setattr(model, "argv", argv)
    assert HouseholdWorker(client, model).run_once() == {"status": "RECORDED"}
    assert len(receipts) == 4
    assert receipts[-1]["usage_status"] == "REPORTED"
    assert len(client.submissions[-1]["metadata"]["model_calls"]) == 2


def test_accounting_rejection_prevents_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    model = CodexHouseholdModel()

    def reject(item: Any) -> None:
        raise CodexUnavailable("ANIMA_MODEL_ACCOUNTING_UNCONFIRMED")

    model.set_model_call_sink(reject)
    monkeypatch.setattr(model, "_capture", lambda *args: pytest.fail("must not launch"))
    with pytest.raises(CodexUnavailable):
        model.run("synthetic", FINAL_SCHEMA)
    assert model.model_calls == []


def test_multiple_completions_and_invalid_usage_are_unknown() -> None:
    valid = stream(FINAL, {"input_tokens": 0, "output_tokens": 0})
    assert CodexHouseholdModel.reported_usage(valid) == {"input_tokens": 0, "output_tokens": 0}
    assert CodexHouseholdModel.reported_usage(valid + b'\n{"type":"turn.completed"}') is None
    assert (
        CodexHouseholdModel.reported_usage(
            stream(FINAL, {"input_tokens": True, "output_tokens": -1, "private": "sentinel"})
        )
        is None
    )


def test_invalid_output_retains_reported_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    model = CodexHouseholdModel()
    monkeypatch.setattr(model, "argv", lambda *args: ["synthetic-cli"])
    monkeypatch.setattr(model, "_capture", lambda *args: (0, stream({}, {"output_tokens": 5}), b""))
    with pytest.raises(CodexUnavailable):
        model.run("synthetic", FINAL_SCHEMA)
    assert model.model_calls[-1]["status"] == "INVALID_RESULT"
    assert model.model_calls[-1]["usage"] == {"output_tokens": 5}


@pytest.mark.parametrize(
    "field", ["call_id", "purpose", "model", "phase", "status", "usage_status"]
)
def test_invalid_metadata_scalar_is_rejected_without_handler_type_error(field: str) -> None:
    from uuid import uuid4

    receipt = {
        "call_id": str(uuid4()),
        "purpose": "PLANNER",
        "model": "gpt-5.6-luna",
        "phase": "ATTEMPTED",
        "status": "UNKNOWN",
        "usage": None,
        "usage_status": "UNKNOWN",
        "elapsed_ms": 0,
    }
    with pytest.raises(ValueError, match="INVALID_MODEL_CALL_RECEIPT"):
        model_call_receipt({**receipt, field: []})
