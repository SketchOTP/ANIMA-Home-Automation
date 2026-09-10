#!/usr/bin/env python3
"""Keep the owner-local Waydroid notification path alive.

This is deliberately a small host supervisor, not an Android management API.
It owns no vendor credentials and never reads notification text.  It starts
only the already commissioned container/session/vendor applications when a
bounded failure is observed, and writes a mode-0600, metadata-only readiness
document for operator diagnostics.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

TAPO_PACKAGE = "com.tplink.iot"
WANSVIEW_PACKAGE = "net.ajcloud.wansviewplus"
VENDOR_PACKAGES = (TAPO_PACKAGE, WANSVIEW_PACKAGE)
VENDOR_ACTIVITIES = {
    TAPO_PACKAGE: "com.tplink.iot/.view.welcome.StartupActivity",
    WANSVIEW_PACKAGE: "net.ajcloud.wansviewplus/.main.welcome.SplashActivity",
}
USER_UNITS = (
    "anima-android-bus.service",
    "anima-android-compositor.service",
    "anima-vendor-notification-relay.service",
    "anima-android-session.service",
)
DEFAULT_STATUS = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / (
    "anima-android-notification-readiness.json"
)
DEFAULT_RELAY_STATUS = Path(
    os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
) / "anima-vendor-relay-status.json"
APP_RESTART_COOLDOWN = 300.0
STATUS_MAX_AGE = 90.0


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str = ""


Runner = Callable[[Sequence[str], float], CommandResult]


def run_command(argv: Sequence[str], timeout: float = 8.0) -> CommandResult:
    try:
        completed = subprocess.run(
            list(argv),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return CommandResult(1)
    # Android diagnostics are parsed in memory for bounded booleans only.  A
    # larger cap avoids truncating package permissions/channels that appear
    # after the package header; nothing from this buffer is logged or stored.
    return CommandResult(completed.returncode, completed.stdout[:262_144])


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _atomic_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _read_private_json(path: Path) -> dict[str, object] | None:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_uid != os.geteuid()
                or info.st_size > 32_768
                or info.st_mode & 0o077
            ):
                return None
            with os.fdopen(descriptor, "r", encoding="utf-8", closefd=False) as stream:
                value = json.load(stream)
        finally:
            os.close(descriptor)
    except (OSError, ValueError, TypeError, UnicodeError):
        return None
    return value if isinstance(value, dict) else None


def _iso_recent(value: object, *, now: float) -> bool:
    if not isinstance(value, str):
        return False
    try:
        observed = datetime.fromisoformat(value).astimezone(UTC).timestamp()
    except (TypeError, ValueError, OverflowError):
        return False
    return 0 <= now - observed <= STATUS_MAX_AGE


class WaydroidSupervisor:
    def __init__(
        self,
        *,
        runner: Runner = run_command,
        status_path: Path = DEFAULT_STATUS,
        relay_status_path: Path = DEFAULT_RELAY_STATUS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.runner = runner
        self.status_path = status_path
        self.relay_status_path = relay_status_path
        self.clock = clock
        self.last_app_launch: dict[str, float] = {}
        self.last_process_observed: dict[str, bool] = {}
        self.last_container_start = 0.0
        self.last_session_start = 0.0

    def _run(self, *argv: str, timeout: float = 8.0) -> CommandResult:
        return self.runner(argv, timeout)

    def _user_active(self, unit: str) -> bool:
        return self._run("systemctl", "--user", "is-active", "--quiet", unit).returncode == 0

    def _system_active(self, unit: str) -> bool:
        return self._run("systemctl", "is-active", "--quiet", unit).returncode == 0

    def _android(self, *argv: str, timeout: float = 8.0) -> CommandResult:
        return self._run("sudo", "-n", "waydroid", "shell", "--", *argv, timeout=timeout)

    def _start_user_unit(self, unit: str) -> bool:
        return self._run("systemctl", "--user", "start", unit, timeout=20).returncode == 0

    def _ensure_services(self) -> dict[str, str]:
        services: dict[str, str] = {}
        for unit in USER_UNITS:
            if self._user_active(unit):
                services[unit.removesuffix(".service")] = "ACTIVE"
            elif self._start_user_unit(unit) and self._user_active(unit):
                services[unit.removesuffix(".service")] = "RECOVERED"
            else:
                services[unit.removesuffix(".service")] = "NOT_READY"
        return services

    def _ensure_container(self) -> str:
        if self._system_active("waydroid-container.service"):
            return "ACTIVE"
        now = self.clock()
        if now - self.last_container_start >= 30:
            self.last_container_start = now
            if self._run(
                "sudo", "-n", "systemctl", "start", "waydroid-container.service", timeout=30
            ).returncode == 0 and self._system_active("waydroid-container.service"):
                return "RECOVERED"
        return "NOT_READY"

    def _ensure_android_session(self) -> str:
        if self._user_active("anima-android-session.service"):
            return "ACTIVE"
        now = self.clock()
        if now - self.last_session_start >= 15:
            self.last_session_start = now
            if self._start_user_unit("anima-android-session.service") and self._user_active(
                "anima-android-session.service"
            ):
                return "RECOVERED"
        return "NOT_READY"

    def _status_lines(self) -> dict[str, str]:
        result = self._run("waydroid", "status")
        values: dict[str, str] = {}
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                key, separator, value = line.partition(":")
                if separator:
                    values[key.strip().casefold().replace(" ", "_")] = value.strip()
        return values

    def _package_dump(self, package: str) -> str:
        return self._android("dumpsys", "package", package, timeout=10).stdout

    def _package_ready(self, package: str) -> dict[str, object]:
        dump = self._package_dump(package)
        package_path = self._android("cmd", "package", "path", package)
        installed = package_path.returncode == 0 and "package:" in package_path.stdout
        user_line = next((line for line in dump.splitlines() if "User 0:" in line), "")
        permission = "android.permission.POST_NOTIFICATIONS: granted=true" in dump
        stopped = "stopped=true" in user_line or "suspended=true" in user_line
        channels = self._notification_channels_ready(package)
        running = self._process_observed(package)
        reasons = []
        if not installed:
            reasons.append("PACKAGE_NOT_INSTALLED")
        if stopped:
            reasons.append("PACKAGE_STOPPED")
        if not permission:
            reasons.append("NOTIFICATION_PERMISSION")
        if not channels:
            reasons.append("NOTIFICATION_CHANNEL")
        if not running:
            reasons.append("PROCESS_NOT_OBSERVED")
        return {
            "state": "READY" if not reasons else "NOT_READY",
            "reason": "OK" if not reasons else "+".join(reasons),
            "installed": installed,
            "stopped": stopped,
            "notification_permission": permission,
            "notification_channels": channels,
            "process_observed": running,
            "launch_eligible": not any(
                (
                    not installed,
                    stopped,
                    not permission,
                    not channels,
                )
            ),
            "account_state": "NOT_EXPOSED",
            "settings_state": "NOT_EXPOSED",
        }

    def _notification_channels_ready(self, package: str) -> bool:
        dump = self._android("dumpsys", "notification", timeout=10).stdout
        marker = f"AppSettings: {package}"
        start = dump.find(marker)
        if start < 0:
            return False
        next_package = dump.find("AppSettings:", start + len(marker))
        section = dump[start : next_package if next_package >= 0 else start + 16_384]
        return "importance=NONE" not in section and any(
            "mImportance=" + str(level) in section for level in (1, 2, 3, 4, 5)
        )

    def _process_observed(self, package: str) -> bool:
        pidof = self._android("pidof", package)
        if pidof.returncode == 0 and pidof.stdout.strip():
            return True
        # Some Android builds return success with an empty pidof result. The
        # activity-manager process table is a bounded, content-free fallback.
        processes = self._android("dumpsys", "activity", "processes", timeout=12)
        return processes.returncode == 0 and package in processes.stdout

    def _launch_vendor_if_needed(self, package: str, package_state: dict[str, object]) -> None:
        now = self.clock()
        if not package_state["launch_eligible"] or package_state["process_observed"]:
            return
        process_died = self.last_process_observed.get(package) is True
        if (
            not process_died
            and now - self.last_app_launch.get(package, 0.0) < APP_RESTART_COOLDOWN
        ):
            return
        if (
            self._android("am", "start", "-n", VENDOR_ACTIVITIES[package], timeout=20).returncode
            == 0
        ):
            self.last_app_launch[package] = now
            self._android("input", "keyevent", "3")

    def _network(self) -> tuple[str, str]:
        gateway = self._android("ping", "-c", "1", "-W", "2", "192.168.240.1", timeout=5)
        if gateway.returncode != 0:
            return "DISCONNECTED", "ANDROID_GATEWAY_UNREACHABLE"
        dns = self._android("ping", "-c", "1", "-W", "3", "example.com", timeout=6)
        return (
            ("CONNECTED", "OK")
            if dns.returncode == 0
            else ("DEGRADED", "DNS_OR_EGRESS_UNAVAILABLE")
        )

    def _clock_state(self) -> str:
        result = self._android("date", "+%s")
        try:
            delta = abs(float(result.stdout.strip()) - self.clock())
        except (TypeError, ValueError):
            return "UNKNOWN"
        return "SANE" if result.returncode == 0 and delta <= 120 else "SKEWED"

    def _fcm_state(self, network: str) -> tuple[str, str]:
        gms = self._android("cmd", "package", "path", "com.google.android.gms")
        if gms.returncode != 0:
            return "DISCONNECTED", "GOOGLE_PLAY_SERVICES_UNAVAILABLE"
        if network != "CONNECTED":
            return "UNKNOWN", "NETWORK_NOT_READY"
        services = self._android("dumpsys", "activity", "services", timeout=12).stdout
        if "cloudmessaging.service.START" in services:
            return "CONNECTED", "CLOUD_MESSAGING_SERVICE_OBSERVED"
        return "UNKNOWN", "FCM_CONNECTION_NOT_EXPOSED_BY_ANDROID"

    def _relay_state(self, services: dict[str, str]) -> tuple[str, str, dict[str, object]]:
        relay = _read_private_json(self.relay_status_path) or {}
        observed = relay.get("observed_at")
        if services.get("anima-vendor-notification-relay") not in {"ACTIVE", "RECOVERED"}:
            return "NOT_READY", "RELAY_SERVICE_INACTIVE", relay
        if not _iso_recent(observed, now=self.clock()):
            return "DEGRADED", "RELAY_HEARTBEAT_STALE", relay
        state = relay.get("state")
        return (
            "CONNECTED",
            "HEARTBEAT" if state in {"READY", "DELIVERED"} else "RELAY_REPORTED_FAILURE",
            relay,
        )

    def run_once(self) -> dict[str, object]:
        container = self._ensure_container()
        services = self._ensure_services() if container in {"ACTIVE", "RECOVERED"} else {}
        session = self._ensure_android_session() if services else "NOT_READY"
        android = self._status_lines() if session in {"ACTIVE", "RECOVERED"} else {}
        if android:
            android["sys_boot_completed"] = self._android(
                "getprop", "sys.boot_completed"
            ).stdout.strip()
            android["dev_bootcomplete"] = self._android(
                "getprop", "dev.bootcomplete"
            ).stdout.strip()
        boot_completed = (
            android.get("sys_boot_completed") == "1" or android.get("dev_bootcomplete") == "1"
        )
        network, network_reason = (
            self._network() if boot_completed else ("UNKNOWN", "ANDROID_NOT_BOOTED")
        )
        clock_state = self._clock_state() if boot_completed else "UNKNOWN"
        fcm, fcm_reason = (
            self._fcm_state(network) if boot_completed else ("UNKNOWN", "ANDROID_NOT_BOOTED")
        )
        vendor_states: dict[str, dict[str, object]] = {}
        if boot_completed:
            for package in VENDOR_PACKAGES:
                package_state = self._package_ready(package)
                self._launch_vendor_if_needed(package, package_state)
                self.last_process_observed[package] = bool(package_state["process_observed"])
                vendor_states[package] = package_state
        else:
            for package in VENDOR_PACKAGES:
                vendor_states[package] = {"state": "NOT_READY", "reason": "ANDROID_NOT_BOOTED"}
        relay, relay_reason, relay_metadata = self._relay_state(services)
        listener = (
            ("CONNECTED", "WAYDROID_PRIVATE_DBUS_FORWARDER")
            if relay in {"CONNECTED", "DEGRADED"}
            else ("NOT_READY", "RELAY_NOT_CONNECTED")
        )
        vendor_ready = all(item.get("state") == "READY" for item in vendor_states.values())
        component_states = {
            "waydroid_container": {
                "state": "READY" if container in {"ACTIVE", "RECOVERED"} else container
            },
            "android_session": {
                "state": "READY" if session in {"ACTIVE", "RECOVERED"} else session
            },
            "network": {"state": network, "reason": network_reason},
            "dns": {"state": "READY" if network == "CONNECTED" else network},
            "clock": {"state": clock_state},
            "fcm": {"state": fcm, "reason": fcm_reason},
            "notification_listener": {"state": listener[0], "reason": listener[1]},
            "relay": {"state": relay, "reason": relay_reason},
            "vendors": vendor_states,
        }
        core_ready = (
            container in {"ACTIVE", "RECOVERED"}
            and session in {"ACTIVE", "RECOVERED"}
            and boot_completed
            and network == "CONNECTED"
            and clock_state == "SANE"
            and fcm == "CONNECTED"
            and relay == "CONNECTED"
            and listener[0] == "CONNECTED"
            and vendor_ready
        )
        overall_state = "READY" if core_ready else "DEGRADED" if boot_completed else "NOT_READY"
        payload: dict[str, object] = {
            "version": 1,
            "observed_at": _now(),
            "state": overall_state,
            "services": services,
            "android": {"boot_completed": boot_completed, **android},
            "components": component_states,
            "relay_counters": {
                key: relay_metadata[key]
                for key in (
                    "received",
                    "accepted",
                    "rejected",
                    "failed",
                    "received_by_package",
                    "accepted_by_package",
                )
                if key in relay_metadata
            },
        }
        _atomic_json(self.status_path, payload)
        return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=15.0)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--relay-status", type=Path, default=DEFAULT_RELAY_STATUS)
    args = parser.parse_args(argv)
    if args.interval < 5 or args.interval > 300:
        raise SystemExit("interval must be between 5 and 300 seconds")
    supervisor = WaydroidSupervisor(
        status_path=args.status, relay_status_path=args.relay_status
    )
    while True:
        supervisor.run_once()
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
