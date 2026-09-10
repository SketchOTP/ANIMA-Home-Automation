"""Tests for the metadata-only Waydroid notification supervisor."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any


def supervisor_module() -> Any:
    path = Path(__file__).parents[1] / "scripts" / "waydroid_notification_supervisor.py"
    spec = importlib.util.spec_from_file_location("waydroid_notification_supervisor", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_private_status_rejects_symlink_and_permissive_file(tmp_path: Path) -> None:
    module = supervisor_module()
    target = tmp_path / "status.json"
    target.write_text("{}", encoding="utf-8")
    target.chmod(0o600)
    link = tmp_path / "link.json"
    link.symlink_to(target)
    assert module._read_private_json(link) is None
    target.chmod(0o644)
    assert module._read_private_json(target) is None


def test_run_once_recovers_ready_stack_without_model_or_notification_payload(
    tmp_path: Path,
) -> None:
    module = supervisor_module()
    relay_status = tmp_path / "relay.json"
    relay_status.write_text(
        json.dumps(
            {
                "version": 1,
                "state": "READY",
                "observed_at": "2026-09-10T12:00:00+00:00",
                "received": 4,
                "accepted": 4,
                "rejected": 0,
                "failed": 0,
                "received_by_package": {module.TAPO_PACKAGE: 2},
                "accepted_by_package": {module.TAPO_PACKAGE: 2},
            }
        ),
        encoding="utf-8",
    )
    relay_status.chmod(0o600)
    calls: list[tuple[str, ...]] = []
    running_packages: set[str] = set()

    package_dump = (
        "Package [com.tplink.iot]\n"
        "  User 0: installed=true stopped=false suspended=false notLaunched=false\n"
        "    android.permission.POST_NOTIFICATIONS: granted=true\n"
    )
    notification_dump = (
        "AppSettings: com.tplink.iot (10150) importance=DEFAULT userSet=true\n"
        "  NotificationChannel{mId='door' mImportance=4}\n"
        "AppSettings: net.ajcloud.wansviewplus (10148) importance=DEFAULT userSet=true\n"
        "  NotificationChannel{mId='alarm' mImportance=4}\n"
    )

    def runner(argv: Sequence[str], timeout: float) -> Any:
        del timeout
        command = tuple(argv)
        calls.append(command)
        if command[:4] == ("systemctl", "--user", "is-active", "--quiet"):
            return module.CommandResult(0)
        if command[:4] == ("systemctl", "is-active", "--quiet", "waydroid-container.service"):
            return module.CommandResult(0)
        if command[:5] == ("sudo", "-n", "systemctl", "is-active", "--quiet"):
            return module.CommandResult(0)
        if command == ("waydroid", "status"):
            return module.CommandResult(
                0,
                "Session: RUNNING\nContainer: RUNNING\nIP address: 192.168.240.112\n",
            )
        if command[0:4] == ("sudo", "-n", "waydroid", "shell"):
            android_command = command[5:]
            if android_command[:2] == ("getprop", "sys.boot_completed"):
                return module.CommandResult(0, "1\n")
            if android_command[:2] == ("getprop", "dev.bootcomplete"):
                return module.CommandResult(0, "1\n")
            if android_command[:2] == ("ping", "-c"):
                return module.CommandResult(0)
            if android_command[:2] == ("date", "+%s"):
                return module.CommandResult(0, "1789041600\n")
            if android_command[:3] == ("cmd", "package", "path"):
                return module.CommandResult(0, "package:/data/app/base.apk\n")
            if android_command[:2] == ("dumpsys", "package"):
                return module.CommandResult(0, package_dump)
            if android_command[:2] == ("dumpsys", "notification"):
                return module.CommandResult(0, notification_dump)
            if android_command[:3] == ("dumpsys", "activity", "services"):
                return module.CommandResult(
                    0,
                    "dat=chimera-action:com.google.android.gms.cloudmessaging.service.START",
                )
            if android_command[:3] == ("dumpsys", "activity", "processes"):
                return module.CommandResult(0, "\n".join(sorted(running_packages)))
            if android_command[:1] == ("pidof",):
                return module.CommandResult(0)
            if android_command[:3] == ("am", "start", "-n"):
                running_packages.add(android_command[3].split("/", 1)[0])
                return module.CommandResult(0)
            return module.CommandResult(0)
        raise AssertionError(f"unexpected command: {command}")

    def clock() -> float:
        return 1_789_041_600.0

    supervisor = module.WaydroidSupervisor(
        runner=runner,
        status_path=tmp_path / "readiness.json",
        relay_status_path=relay_status,
        clock=clock,
    )
    payload = supervisor.run_once()
    assert payload["state"] == "DEGRADED"
    assert payload["components"]["fcm"] == {
        "state": "CONNECTED",
        "reason": "CLOUD_MESSAGING_SERVICE_OBSERVED",
    }
    vendors = payload["components"]["vendors"]
    assert vendors[module.TAPO_PACKAGE]["state"] == "NOT_READY"
    assert vendors[module.WANSVIEW_PACKAGE]["state"] == "NOT_READY"
    assert vendors[module.TAPO_PACKAGE]["reason"] == "PROCESS_NOT_OBSERVED"
    assert sum(command[5:7] == ("am", "start") for command in calls) == 2
    payload = supervisor.run_once()
    assert payload["state"] == "READY"
    assert all(item["state"] == "READY" for item in payload["components"]["vendors"].values())
    running_packages.remove(module.TAPO_PACKAGE)
    payload = supervisor.run_once()
    assert payload["components"]["vendors"][module.TAPO_PACKAGE]["state"] == "NOT_READY"
    assert sum(command[5:7] == ("am", "start") for command in calls) == 3
    assert (tmp_path / "readiness.json").stat().st_mode & 0o777 == 0o600
    encoded = (tmp_path / "readiness.json").read_text(encoding="utf-8")
    assert "notification body" not in encoded
