import importlib.util
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
