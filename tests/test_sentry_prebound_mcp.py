"""Private host bindings for the existing voice resident; no live service calls."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "integrations/sentry/anima-household"
SAFE: dict[str, Any] = {"tool_id": "anima.household.read", "availability": True}
PRODUCTS = (
    "anima.external.shopping.search_products",
    "anima.external.shopping.bestbuy.search_products",
    "anima.external.shopping.upcitemdb.search_products",
)


class Client:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.catalogue = [deepcopy(SAFE)]
        self.result: dict[str, Any] = {"status": "SUCCEEDED", "value": "synthetic"}
        self.fail = False

    def call(self, path: str) -> dict[str, Any]:
        self.calls.append(("health", path))
        return {"state": "available"}

    def context(self, request: str, binding: str) -> dict[str, Any]:
        self.calls.append(("context", request, binding))
        return {"context": "synthetic"}

    def tools(self, request: str, binding: str) -> dict[str, Any]:
        self.calls.append(("tools", request, binding))
        return {"tools": self.catalogue}

    def invoke(self, *args: Any) -> dict[str, Any]:
        self.calls.append(("invoke", *args))
        if self.fail:
            raise RuntimeError("synthetic transport failure")
        return deepcopy(self.result)

    def status(self, request: str, binding: str) -> dict[str, Any]:
        self.calls.append(("status", request, binding))
        return {"status": "PROVIDER_RUNNING"}

    def open_interaction(self, *args: Any) -> dict[str, Any]:
        self.calls.append(("open", *args))
        return {"status": "CLAIMED", "request_id": "legacy", "binding": "synthetic"}

    def open_direct_interaction(self, *args: Any) -> dict[str, Any]:
        return self.open_interaction(*args)

    def provider_start(self, *args: Any) -> dict[str, Any]:
        self.calls.append(("start", *args))
        return {"status": "PROVIDER_RUNNING"}

    def renew(self, *args: Any) -> dict[str, Any]:
        self.calls.append(("renew", *args))
        return {"status": "RENEWED"}

    def submit_result(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("submit", *args))
        return {"status": "RECORDED"}


def load(monkeypatch: pytest.MonkeyPatch, binding_path: Path | None) -> Any:
    monkeypatch.syspath_prepend(str(PACKAGE))
    if binding_path is None:
        monkeypatch.delenv("ANIMA_PREBOUND_FILE", raising=False)
    else:
        monkeypatch.setenv("ANIMA_PREBOUND_FILE", str(binding_path))
    spec = importlib.util.spec_from_file_location(
        f"prebound_{uuid4().hex}", PACKAGE / "anima_household_mcp.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    workspace, private = tmp_path / "workspace", tmp_path / "private"
    workspace.mkdir()
    private.mkdir(mode=0o700)
    token = private / "client.token"
    token.touch(mode=0o600)
    payload = {
        "version": 1,
        "request_id": str(uuid4()),
        "binding": "SYNTHETIC_PRIVATE_BINDING",
        "sentry_request_id": str(uuid4()),
        "source_surface": "always_on_voice",
        "endpoint": "/synthetic/core.sock",
        "token_file": str(token),
        "worker_id": "synthetic",
        "expires_at": (datetime.now(UTC) + timedelta(seconds=270)).isoformat(),
        "persistent_thread": True,
        "workspace_root": str(workspace.resolve()),
    }
    path = private / "binding.json"
    path.write_text(json.dumps(payload))
    path.chmod(0o600)
    metadata = private / "metadata.json"
    metadata.write_text(json.dumps({"version": 1, "status": "READY", "calls": 0}))
    metadata.chmod(0o600)
    module = load(monkeypatch, path)
    client = Client()
    module._CLIENT = client
    return module, client, path, payload, metadata


def test_prebound_registers_only_request_bound_tools_and_no_secret_arguments(bound: Any) -> None:
    module, client, _, payload, _ = bound
    tools = asyncio.run(module.server.list_tools())
    assert {tool.name for tool in tools} == {
        "anima_health",
        "anima_get_context",
        "anima_list_tools",
        "anima_invoke",
        "anima_status",
    }
    serialized = json.dumps([tool.model_dump() for tool in tools])
    assert payload["binding"] not in serialized and payload["token_file"] not in serialized
    assert all("binding" not in tool.input_schema.get("properties", {}) for tool in tools)
    module.anima_get_context(payload["request_id"])
    assert client.calls[-1] == ("context", payload["request_id"], payload["binding"])
    health = module.anima_health()
    assert health == {"state": "available", "request_id": payload["request_id"]}
    assert payload["binding"] not in json.dumps(health)
    assert payload["token_file"] not in json.dumps(health)


def test_mcp_annotations_distinguish_reads_from_governed_invocation(bound: Any) -> None:
    module, *_ = bound
    tools = asyncio.run(module.server.list_tools())
    for tool in tools:
        assert tool.annotations is not None
        annotations = tool.annotations.model_dump(by_alias=True)
        assert annotations["readOnlyHint"] is (tool.name != "anima_invoke")
        assert annotations["destructiveHint"] is (tool.name == "anima_invoke")


@pytest.mark.parametrize(
    "operation,args",
    [
        ("anima_open_interaction", ("id",)),
        ("anima_open_direct_interaction", ("id", "voice transcript")),
        ("anima_provider_start", ("id",)),
        ("anima_renew", ("id",)),
        ("anima_submit_result", ("id", "RESPONSE")),
    ],
)
def test_prebound_lifecycle_rejected_even_if_called_directly(
    bound: Any, operation: str, args: tuple[Any, ...]
) -> None:
    module, client, *_ = bound
    with pytest.raises(RuntimeError, match="HOST_OWNS_LIFECYCLE"):
        getattr(module, operation)(*args)
    assert client.calls == []


@pytest.mark.parametrize(
    "operation", ["anima_get_context", "anima_list_tools", "anima_status", "anima_invoke"]
)
def test_foreign_request_never_reaches_service(bound: Any, operation: str) -> None:
    module, client, *_ = bound
    args: tuple[Any, ...] = (
        (str(uuid4()), SAFE["tool_id"], {}) if operation == "anima_invoke" else (str(uuid4()),)
    )
    with pytest.raises(RuntimeError, match="REQUEST_MISMATCH"):
        getattr(module, operation)(*args)
    assert client.calls == []


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "symlink",
        "public",
        "directory",
        "parent-public",
        "inside-workspace",
        "token-inside",
        "expired",
        "naive",
        "version",
        "persistent",
        "extra",
        "huge",
        "malformed",
    ],
)
def test_private_binding_validation_fails_closed(bound: Any, case: str) -> None:
    module, client, path, payload, _ = bound
    if case == "missing":
        path.unlink()
    elif case == "symlink":
        target = path.with_name("target.json")
        path.rename(target)
        path.symlink_to(target)
    elif case == "public":
        path.chmod(0o640)
    elif case == "directory":
        path.unlink()
        path.mkdir()
    elif case == "parent-public":
        path.parent.chmod(0o755)
    elif case in {"huge", "malformed"}:
        path.write_text("x" * (65537 if case == "huge" else 1))
    else:
        if case == "inside-workspace":
            payload["workspace_root"] = str(path.parent)
        elif case == "token-inside":
            payload["token_file"] = str(Path(payload["workspace_root"]) / "token")
        elif case == "expired":
            payload["expires_at"] = "2020-01-01T00:00:00+00:00"
        elif case == "naive":
            payload["expires_at"] = "2099-01-01T00:00:00"
        elif case == "version":
            payload["version"] = True
        elif case == "persistent":
            payload["persistent_thread"] = False
        else:
            payload["authority"] = "OWNER"
        path.write_text(json.dumps(payload))
    with pytest.raises(RuntimeError, match="PREBOUND_FILE_INVALID"):
        module.anima_health()
    assert client.calls == []


def test_client_configuration_is_host_owned(bound: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    module, client, _, payload, _ = bound
    module._CLIENT = None
    seen: list[Any] = []

    def construct(**kwargs: Any) -> Any:
        seen.append(kwargs)
        return client

    monkeypatch.setattr(module, "AnimaHouseholdClient", construct)
    module.anima_health()
    assert seen == [{"endpoint": payload["endpoint"], "token_file": payload["token_file"]}]


@pytest.mark.parametrize("case", ["removed", "rebound", "expired"])
def test_cached_client_cannot_bypass_host_revocation(bound: Any, case: str) -> None:
    module, client, path, payload, _ = bound
    module.anima_health()
    client.calls.clear()
    if case == "removed":
        path.unlink()
    else:
        payload["binding" if case == "rebound" else "expires_at"] = (
            "other" if case == "rebound" else "2020-01-01T00:00:00Z"
        )
        path.write_text(json.dumps(payload))
    with pytest.raises(RuntimeError):
        module.anima_invoke(payload["request_id"], SAFE["tool_id"], {})
    assert client.calls == []


@pytest.mark.parametrize("tool_id", PRODUCTS + ("future.restricted",))
def test_restricted_products_filtered_and_blocked_before_invoke(bound: Any, tool_id: str) -> None:
    module, client, _, payload, metadata = bound
    descriptor = {"tool_id": tool_id, "availability": True, "description": "NEVER_EGRESS"}
    if tool_id == "future.restricted":
        descriptor["content_persistence"] = "EPHEMERAL_RESTRICTED"
    client.catalogue.append(descriptor)
    catalogue = module.anima_list_tools(payload["request_id"])
    assert catalogue["tools"] == [SAFE]
    assert "NEVER_EGRESS" not in json.dumps(catalogue)
    assert (
        catalogue["unavailable_tools"][0]["unavailable_reason"]
        == "PERSISTENT_THREAD_RESTRICTED_CONTENT"
    )
    assert module.anima_invoke(payload["request_id"], tool_id, {})["status"] == "UNAVAILABLE"
    assert not any(call[0] == "invoke" for call in client.calls)
    assert json.loads(metadata.read_text()) == {"version": 1, "status": "UNAVAILABLE", "calls": 0}


def test_ordinal_idempotence_concurrent_retry_conflict_and_restart(
    bound: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, client, path, payload, metadata = bound
    args = (payload["request_id"], SAFE["tool_id"], {"synthetic": "ARGUMENT_NOT_PERSISTED"})
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: module.anima_invoke(*args, ordinal=1), range(2)))
    assert results[0] == results[1]
    assert sum(call[0] == "invoke" for call in client.calls) == 1
    assert json.loads(metadata.read_text()) == {"version": 1, "status": "SUCCEEDED", "calls": 1}
    assert metadata.stat().st_mode & 0o777 == 0o600
    with pytest.raises(RuntimeError, match="ALREADY_DISPATCHED"):
        module.anima_invoke(payload["request_id"], SAFE["tool_id"], {"changed": True}, ordinal=1)
    restarted = load(monkeypatch, path)
    restarted._CLIENT = client
    with pytest.raises(RuntimeError, match="ORDINAL_INVALID"):
        restarted.anima_invoke(*args, ordinal=1)
    assert sum(call[0] == "invoke" for call in client.calls) == 1


def test_ambiguous_dispatch_never_retries_and_host_records_unknown(bound: Any) -> None:
    module, client, _, payload, metadata = bound
    client.fail = True
    args: tuple[str, str, dict[str, Any]] = (payload["request_id"], SAFE["tool_id"], {})
    with pytest.raises(RuntimeError):
        module.anima_invoke(*args)
    client.fail = False
    with pytest.raises(RuntimeError, match="ALREADY_DISPATCHED"):
        module.anima_invoke(*args)
    assert json.loads(metadata.read_text()) == {
        "version": 1,
        "status": "UNKNOWN_RESULT",
        "calls": 1,
    }
    assert sum(call[0] == "invoke" for call in client.calls) == 1


@pytest.mark.parametrize(
    "status", ["PARTIAL", "WAITING_CONFIRMATION", "WAITING_STRONGER_AUTH", "FAILED", "UNAVAILABLE"]
)
def test_gated_status_is_sticky_not_model_overridable(bound: Any, status: str) -> None:
    module, client, _, payload, metadata = bound
    client.result = {"status": status}
    module.anima_invoke(payload["request_id"], SAFE["tool_id"], {}, ordinal=1)
    client.result = {"status": "SUCCEEDED"}
    with pytest.raises(RuntimeError, match="TURN_BLOCKED"):
        module.anima_invoke(payload["request_id"], SAFE["tool_id"], {}, ordinal=2)
    assert json.loads(metadata.read_text())["status"] == status
    assert sum(call[0] == "invoke" for call in client.calls) == 1


def test_unexpected_restricted_result_never_enters_persistent_thread(bound: Any) -> None:
    module, client, _, payload, metadata = bound
    client.result = {
        "status": "SUCCEEDED",
        "products": ["PRIVATE_PRODUCT"],
        "metadata": {"content_class": "EPHEMERAL_RESTRICTED"},
    }
    result = module.anima_invoke(payload["request_id"], SAFE["tool_id"], {})
    assert result == {"status": "UNAVAILABLE", "reason": "PERSISTENT_THREAD_RESTRICTED_CONTENT"}
    assert "PRIVATE_PRODUCT" not in repr(module._CALLS)
    assert json.loads(metadata.read_text())["status"] == "UNAVAILABLE"


def test_normal_plugin_mode_preserves_existing_lifecycle_and_catalogue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load(monkeypatch, None)
    client = Client()
    module._CLIENT = client
    assert len(asyncio.run(module.server.list_tools())) == 10
    module.anima_open_interaction("synthetic")
    module.anima_open_direct_interaction("synthetic", "voice transcript")
    module.anima_provider_start("legacy")
    module.anima_renew("legacy")
    module.anima_submit_result("legacy", "RESPONSE")
    client.catalogue = [{"tool_id": PRODUCTS[0], "content_persistence": "EPHEMERAL_RESTRICTED"}]
    assert module.anima_list_tools("legacy") == {"tools": client.catalogue}
    module.anima_invoke("legacy", PRODUCTS[0], {})
    assert [call[0] for call in client.calls] == [
        "open",
        "open",
        "start",
        "renew",
        "submit",
        "tools",
        "invoke",
    ]


@pytest.mark.parametrize("ordinal", [True, False, 0, -1, 9, 1.5, "1"])
def test_invalid_ordinals_never_dispatch(bound: Any, ordinal: Any) -> None:
    module, client, _, payload, _ = bound
    with pytest.raises(RuntimeError, match="ORDINAL_INVALID"):
        module.anima_invoke(payload["request_id"], SAFE["tool_id"], {}, ordinal=ordinal)
    assert client.calls == []


def test_eight_call_budget_is_durable(bound: Any) -> None:
    module, client, _, payload, metadata = bound
    for ordinal in range(1, 9):
        module.anima_invoke(payload["request_id"], SAFE["tool_id"], {}, ordinal=ordinal)
    with pytest.raises(RuntimeError, match="ORDINAL_INVALID"):
        module.anima_invoke(payload["request_id"], SAFE["tool_id"], {}, ordinal=9)
    assert sum(call[0] == "invoke" for call in client.calls) == 8
    assert json.loads(metadata.read_text()) == {"version": 1, "status": "SUCCEEDED", "calls": 8}


@pytest.mark.parametrize("case", ["missing", "public", "symlink", "invalid-count"])
def test_metadata_guard_precedes_dispatch(bound: Any, case: str) -> None:
    module, client, _, payload, metadata = bound
    if case == "missing":
        metadata.unlink()
    elif case == "public":
        metadata.chmod(0o644)
    elif case == "symlink":
        target = metadata.with_name("elsewhere.json")
        metadata.rename(target)
        metadata.symlink_to(target)
    else:
        metadata.write_text(json.dumps({"version": 1, "status": "SUCCEEDED", "calls": 9}))
    with pytest.raises(RuntimeError):
        module.anima_invoke(payload["request_id"], SAFE["tool_id"], {})
    assert client.calls == []


@pytest.mark.parametrize(
    "core_status,host_status",
    [
        ("REQUIRE_CONFIRMATION", "WAITING_CONFIRMATION"),
        ("REQUIRE_STRONGER_AUTH", "WAITING_STRONGER_AUTH"),
        ("DENIED", "FAILED"),
        ("POLICY_DENIED", "FAILED"),
        ("VERIFICATION_FAILED", "PARTIAL"),
    ],
)
def test_expected_core_gates_are_not_misclassified_unknown(
    bound: Any, core_status: str, host_status: str
) -> None:
    module, client, _, payload, metadata = bound
    client.result = {"status": core_status}
    result = module.anima_invoke(payload["request_id"], SAFE["tool_id"], {})
    assert result["status"] == core_status
    assert json.loads(metadata.read_text())["status"] == host_status
    with pytest.raises(RuntimeError, match="TURN_BLOCKED"):
        module.anima_invoke(payload["request_id"], SAFE["tool_id"], {}, ordinal=2)


def test_catalogue_is_frozen_for_turn_and_cannot_gain_tools(bound: Any) -> None:
    module, client, _, payload, _ = bound
    first = module.anima_list_tools(payload["request_id"])
    client.catalogue.append({"tool_id": "newly.added", "availability": True})
    first["tools"].append({"tool_id": "caller.injected", "availability": True})
    assert module.anima_list_tools(payload["request_id"])["tools"] == [SAFE]
    assert module.anima_invoke(payload["request_id"], "newly.added", {})["status"] == "UNAVAILABLE"
    assert sum(call[0] == "tools" for call in client.calls) == 1
    assert not any(call[0] == "invoke" for call in client.calls)


def test_restricted_read_marks_host_unavailable_without_leaking_content(
    bound: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, client, _, payload, metadata = bound
    monkeypatch.setattr(
        client,
        "context",
        lambda *args: {
            "content_persistence": "EPHEMERAL_RESTRICTED",
            "products": ["NEVER_PERSIST"],
        },
    )
    result = module.anima_get_context(payload["request_id"])
    assert result == {"status": "UNAVAILABLE", "reason": "PERSISTENT_THREAD_RESTRICTED_CONTENT"}
    assert json.loads(metadata.read_text()) == {"version": 1, "status": "UNAVAILABLE", "calls": 0}
    with pytest.raises(RuntimeError, match="TURN_BLOCKED"):
        module.anima_invoke(payload["request_id"], SAFE["tool_id"], {})
