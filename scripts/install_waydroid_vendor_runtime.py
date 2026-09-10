#!/usr/bin/env python3
"""Install the owner-local, private Waydroid notification runtime.

This installer writes private configuration and owner-scoped user units. It
does not handle vendor credentials or modify Android app data. The one
privileged operation is enabling the already-installed Waydroid container unit
so the notification appliance has a boot owner; no vendor or Android data is
created by that operation.
"""

# Systemd unit directives are intentionally kept as single lines.
# ruff: noqa: E501

from __future__ import annotations

import json
import os
import secrets
import subprocess
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
CONFIG_ROOT = Path.home() / ".config" / "anima"
UNIT_ROOT = Path.home() / ".config" / "systemd" / "user"
RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
RELAY = PROJECT / "scripts" / "waydroid_vendor_relay.py"
SUPERVISOR = PROJECT / "scripts" / "waydroid_notification_supervisor.py"
CONFIG = CONFIG_ROOT / "waydroid-vendor-relay.json"
TOKEN = CONFIG_ROOT / "waydroid-vendor-relay.token"
STATUS = RUNTIME / "anima-vendor-relay-status.json"
READINESS = RUNTIME / "anima-android-notification-readiness.json"
CAPTURE = RUNTIME / "anima-vendor-qualification.jsonl"


def atomic_private(path: Path, content: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def write_unit(name: str, content: str) -> None:
    path = UNIT_ROOT / name
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    enabled = subprocess.run(
        ["sudo", "-n", "systemctl", "enable", "waydroid-container.service"], check=False
    )
    if enabled.returncode:
        raise SystemExit("could not enable waydroid-container.service without prompting")
    active = subprocess.run(
        ["sudo", "-n", "systemctl", "is-active", "--quiet", "waydroid-container.service"], check=False
    )
    if active.returncode:
        started = subprocess.run(
            ["sudo", "-n", "systemctl", "start", "waydroid-container.service"], check=False
        )
        if started.returncode:
            raise SystemExit("waydroid-container.service could not be started")
    if not TOKEN.exists():
        atomic_private(TOKEN, secrets.token_urlsafe(48) + "\n")
    else:
        os.chmod(TOKEN, 0o600)
    if not CONFIG.exists():
        atomic_private(
            CONFIG,
            json.dumps(
                {
                    "version": 1,
                    "endpoint": "http://127.0.0.1:18090/api/v1/vendor-events/receive",
                    "token_file": str(TOKEN),
                    "status_file": str(STATUS),
                    "capture_file": str(CAPTURE),
                    "capture_limit": 8,
                    "capture_packages": ["com.tplink.iot", "net.ajcloud.wansviewplus"],
                    "rules": [],
                },
                indent=2,
            )
            + "\n",
        )
    os.chmod(CONFIG, 0o600)
    quoted_project = str(PROJECT).replace("%", "%%")
    quoted_config = str(CONFIG).replace("%", "%%")
    quoted_readiness = str(READINESS).replace("%", "%%")
    write_unit(
        "anima-android-bus.service",
        """[Unit]
Description=ANIMA private Android notification bus

[Service]
Type=simple
ExecStart=/usr/bin/dbus-daemon --session --nofork --nopidfile --address=unix:path=%t/anima-android-bus
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
""",
    )
    write_unit(
        "anima-vendor-notification-relay.service",
        f"""[Unit]
Description=ANIMA Tapo and Wansview notification relay
After=anima-android-bus.service
Requires=anima-android-bus.service

[Service]
Type=simple
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=%t/anima-android-bus
ExecStart=/usr/bin/python3 \"{quoted_project}/scripts/waydroid_vendor_relay.py\" --config \"{quoted_config}\"
Restart=on-failure
RestartSec=2
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=%t {CONFIG_ROOT}

[Install]
WantedBy=default.target
""",
    )
    write_unit(
        "anima-android-compositor.service",
        """[Unit]
Description=ANIMA headless Waydroid compositor

[Service]
Type=simple
ExecStart=/usr/bin/weston --backend=headless-backend.so --renderer=pixman --socket=anima-android-wayland --idle-time=0 --no-config --width=1920 --height=1080 --scale=2
Restart=on-failure
RestartSec=2
UMask=0077

[Install]
WantedBy=default.target
""",
    )
    write_unit(
        "anima-android-session.service",
        """[Unit]
Description=ANIMA Waydroid vendor-app session
After=anima-android-bus.service anima-vendor-notification-relay.service anima-android-compositor.service
Requires=anima-android-bus.service anima-vendor-notification-relay.service anima-android-compositor.service

[Service]
Type=simple
Environment=DISPLAY=:1
Environment=WAYLAND_DISPLAY=anima-android-wayland
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=%t/anima-android-bus
Environment=PULSE_RUNTIME_PATH=%t/anima-android-no-audio
ExecStartPre=/usr/bin/install -d -m 700 %t/anima-android-no-audio
ExecStartPre=/usr/bin/install -m 600 /dev/null %t/anima-android-no-audio/native
ExecStart=/usr/bin/waydroid session start
Restart=on-failure
RestartSec=5
UMask=0077

[Install]
WantedBy=default.target
""",
    )
    write_unit(
        "anima-android-notification-supervisor.service",
        f"""[Unit]
Description=ANIMA persistent Android notification readiness supervisor
After=anima-android-session.service anima-vendor-notification-relay.service
Wants=anima-android-session.service anima-vendor-notification-relay.service

[Service]
Type=simple
Environment=PYTHONUNBUFFERED=1
Environment=DISPLAY=:1
Environment=WAYLAND_DISPLAY=anima-android-wayland
Environment=PULSE_RUNTIME_PATH=%t/anima-android-no-audio
ExecStart=/usr/bin/python3 \"{quoted_project}/scripts/waydroid_notification_supervisor.py\" --status \"{quoted_readiness}\" --relay-status \"{str(STATUS).replace('%', '%%')}\"
Restart=on-failure
RestartSec=5
UMask=0077
PrivateUsers=false
PrivateMounts=false

[Install]
WantedBy=default.target
""",
    )
    RUNTIME.joinpath("anima-android-no-audio").mkdir(mode=0o700, exist_ok=True)
    native = RUNTIME / "anima-android-no-audio" / "native"
    if not native.exists():
        native.touch(mode=0o600)
    subprocess.run(
        [
            "systemctl",
            "--user",
            "stop",
            "anima-android-session.service",
            "anima-android-notification-supervisor.service",
            "anima-vendor-notification-relay.service",
            "anima-android-bus.service",
            "anima-android-compositor.service",
        ],
        check=False,
    )
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(
        [
            "systemctl",
            "--user",
            "enable",
            "--now",
            "anima-android-bus.service",
            "anima-vendor-notification-relay.service",
            "anima-android-compositor.service",
            "anima-android-session.service",
            "anima-android-notification-supervisor.service",
        ],
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
