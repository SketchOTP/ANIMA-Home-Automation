"""Opt-in exact user sandbox fixture; only a newly created runtime directory is written."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest


def test_relay_real_installed_sandbox_path_anchor_lock_and_fsync() -> None:
    if os.environ.get("ANIMA_STAGE3_SANDBOX_TEST") != "1":
        pytest.skip("requires explicit local user-systemd sandbox qualification")
    source = (Path(__file__).parents[1] / "scripts/waydroid_vendor_relay.py").read_text()
    # PrivateTmp hides the worktree. Pass secret-free source bytes, not a copy
    # of live source/config. The fixture owns no production bus or endpoint.
    program = f"""
import errno,json,os,sys,tempfile,types
from pathlib import Path
module=types.ModuleType('isolated_relay')
sys.modules[module.__name__]=module
exec(compile({source!r},'isolated_reviewed_relay.py','exec'),module.__dict__)
runtime=Path('/run/user/{os.getuid()}')
with tempfile.TemporaryDirectory(prefix='anima-stage3-sandbox-',dir=runtime) as directory:
    root=Path(directory)
    token=root/'isolated.token'
    token.write_text('isolated-test-only')
    token.chmod(0o600)
    config=module.Config('http://127.0.0.1/never-called',token,root/'status.json',None,0,frozenset(),())
    try:
        fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    except OSError as exc:
        read_errno=exc.errno
    else:
        os.close(fd)
        read_errno=None
    fd=os.open('/',os.O_PATH|os.O_DIRECTORY|os.O_NOFOLLOW)
    root_uid=os.fstat(fd).st_uid
    os.close(fd)
    first=module.Relay(config)
    try:
        try:
            second=module.Relay(config)
        except (module.RelayConfigurationError, BlockingIOError):
            collision=True
        else:
            second.close()
            collision=False
        first._persist()
        assert first.outbox_path.stat().st_mode & 0o777 == 0o600
    finally:
        first.close()
    recovered=module.Relay(config)
    recovered.close()
    print(json.dumps(dict(root_read_errno=read_errno,root_path_uid=root_uid,collision_blocked=collision,
                         fsync_persisted=True,reopen_succeeded=True)))
"""
    result = subprocess.run(
        [
            "systemd-run",
            "--user",
            "--wait",
            "--pipe",
            "--collect",
            f"--unit=anima-stage3-isolated-relay-{uuid4().hex[:12]}",
            "-p",
            "ProtectSystem=strict",
            "-p",
            "ProtectHome=read-only",
            "-p",
            "PrivateTmp=yes",
            "-p",
            "NoNewPrivileges=yes",
            "-p",
            f"ReadWritePaths=/run/user/{os.getuid()}",
            "/usr/bin/python3",
            "-c",
            program,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    proof = json.loads(result.stdout.strip().splitlines()[-1])
    assert proof["root_read_errno"] == 13 and proof["root_path_uid"] == 65534
    assert proof["collision_blocked"] and proof["fsync_persisted"] and proof["reopen_succeeded"]


def test_relay_startup_fault_is_visible_and_restart_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_stage2_relay_outbox import configuration
    from test_waydroid_vendor_relay import relay_module

    module = relay_module()
    config = configuration(module, tmp_path)
    monkeypatch.setattr(module, "load_config", lambda _: config)
    monkeypatch.setattr(module, "serve", lambda _: (_ for _ in ()).throw(PermissionError()))
    monkeypatch.setattr(module.sys, "argv", ["relay", "--config", "isolated"])
    assert module.main() == 2
    status = json.loads(config.status_file.read_text())
    assert status["state"] == "NOT_READY" and status["delivery_state"] == "FAULT"
    assert status["fault"] == "PermissionError"
    template = (
        Path(__file__).parents[1] / "scripts/install_waydroid_vendor_runtime.py"
    ).read_text()
    assert "RestartPreventExitStatus=2" in template
    assert "StartLimitBurst=3" in template
