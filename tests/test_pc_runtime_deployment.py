import importlib.util
import json
import shlex
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


def load_script(name: str) -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


check_pc_readiness = load_script("check_pc_readiness")
install_pc_runtime = load_script("install_pc_runtime")


def test_deployment_is_exact_bounded_copy_with_no_credentials_or_graft(tmp_path: Path) -> None:
    files = install_pc_runtime.deployment_files(tmp_path)
    assert len(files) == 11
    assert not any(
        "graft" in str(path) or "token" in path.name or path.name == ".env" for path in files
    )
    token = tmp_path / ".local/share/anima-household-client/client.token"
    token.parent.mkdir(parents=True)
    token.write_text("preserved")
    install_pc_runtime.install_files(files)
    assert all(path.read_bytes() == content for path, content in files.items())
    assert token.read_text() == "preserved"
    unit = (tmp_path / ".config/systemd/user/anima-pc.service").read_text()
    assert "After=default.target" not in unit
    assert "--wait --wait-timeout 90" in unit
    assert "ExecStartPost=" in unit
    assert "ExecStartPost=" in (tmp_path / ".config/systemd/user/anima-core.service").read_text()
    core = (tmp_path / ".config/systemd/user/anima-core.service").read_text()
    assert "EnvironmentFile=" in core  # commissioned operator override, still loader-validated
    assert "ANIMA_VENDOR_RELAY_CONFIG=%h/.config/anima/vendor-relay-credential.json" in core
    assert (
        "ANIMA_VENDOR_RELAY_CONFIG=%h/.local/share/anima-owner-boundary/vendor-relay.json"
        not in core
    )


def test_preflight_symlink_blocks_all_writes(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_text("preserve")
    link = tmp_path / "link"
    link.symlink_to(target)
    first = tmp_path / "first"
    with pytest.raises(ValueError, match="unsafe"):
        install_pc_runtime.install_files({first: b"new", link: b"bad"})
    assert not first.exists()
    assert target.read_text() == "preserve"


def test_core_readiness_requires_authenticated_health_not_listening(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    client = Mock()
    factory = Mock(return_value=client)
    monkeypatch.setitem(sys.modules, "anima_household_client", Mock(AnimaHouseholdClient=factory))
    monkeypatch.setenv("ANIMA_SENTRY_SOCKET", "/test/core.sock")
    monkeypatch.setenv("ANIMA_SENTRY_SERVICE_TOKEN_FILE", "/test/private.token")
    client.call.return_value = {"provider_id": "anima-core", "state": "available"}
    check_pc_readiness.check_core()
    client.call.assert_called_once_with("/v1/health")
    client.call.return_value = {"state": "listening"}
    with pytest.raises(ValueError, match="not ready"):
        check_pc_readiness.check_core()


def test_binder_candidate_is_only_dynamic_binder_allow() -> None:
    path = (
        Path(__file__).parents[1]
        / "deploy/systemd/system/waydroid-container.service.d/anima-binder.conf"
    )
    lines = [line for line in path.read_text().splitlines() if line and not line.startswith("#")]
    assert lines == ["[Service]", "DeviceAllow=char-binder rw"]


def test_core_launch_preserves_operator_ha_instance_and_drops_only_db_password() -> None:
    from uuid import uuid4

    unit = (Path(__file__).parents[1] / "deploy/systemd/user/anima-core.service").read_text()
    assert "Environment=ANIMA_HA_INSTANCE_ID=" not in unit
    assert "EnvironmentFile=/home/sketch/.config/anima/anima-project.env" in unit
    start = next(
        line.removeprefix("ExecStart=")
        for line in unit.splitlines()
        if line.startswith("ExecStart=")
    )
    argv = shlex.split(start)
    assert argv[:2] == ["/bin/sh", "-c"]
    script = (
        "import os,json; print(json.dumps({"
        "'instance':os.environ.get('ANIMA_HA_INSTANCE_ID'),"
        "'db_password_present':'ANIMA_DB_PASSWORD' in os.environ}))"
    )
    # Isolated shell composition only; no Core process or database connection.
    argv[2] = (
        argv[2].split("exec ", 1)[0]
        + f"exec {shlex.quote(sys.executable)} -c {shlex.quote(script)}"
    )
    identifier = str(uuid4())
    result = subprocess.run(
        argv,
        env={
            "PATH": "/usr/bin:/bin",
            "ANIMA_HA_INSTANCE_ID": identifier,
            "ANIMA_DB_USER": "fixture",
            "ANIMA_DB_PASSWORD": "test-only",
            "ANIMA_DB_NAME": "fixture",
        },
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    assert json.loads(result.stdout) == {"instance": identifier, "db_password_present": False}


def test_later_operator_environment_file_overrides_stale_endpoints_not_identity() -> None:
    from uuid import uuid4

    # Test-only values. Systemd EnvironmentFile values override Environment;
    # later files override earlier files. Parent separately measured this with
    # systemd-run; this fixture tests the launch shell's preservation, not PID1.
    instance = str(uuid4())
    unit_defaults = {"ANIMA_HA_BASE_URL": "http://127.0.0.1:8123"}
    retained_project_file = {
        "ANIMA_HA_INSTANCE_ID": instance,
        "ANIMA_HA_BASE_URL": "http://obsolete.invalid",
        "ANIMA_HA_WEBSOCKET_URL": "ws://obsolete.invalid/api/websocket",
    }
    operator_file = {
        "ANIMA_HA_INSTANCE_ID": instance,
        "ANIMA_HA_BASE_URL": "http://127.0.0.1:8123",
        "ANIMA_HA_WEBSOCKET_URL": "ws://127.0.0.1:8123/api/websocket",
        "ANIMA_HA_EXPECTED_VERSION": "fixture-version",
    }
    effective = {**unit_defaults, **retained_project_file, **operator_file}
    result = subprocess.run(
        [sys.executable, "-c", "import os,json; print(json.dumps(dict(os.environ)))"],
        env=effective,
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    loaded = json.loads(result.stdout)
    assert all(loaded[key] == value for key, value in operator_file.items())
    assert retained_project_file["ANIMA_HA_BASE_URL"] == "http://obsolete.invalid"
