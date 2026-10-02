#!/usr/bin/python3
"""Private Waydroid notification sink for the owner-authorized vendor apps.

The process owns ``org.freedesktop.Notifications`` on a dedicated session bus.
It rejects every package except the configured Tapo and Wansview package before
examining notification text, converts matched rules to ANIMA's minimized typed
report, and never forwards images, actions, links, or raw notification text.

Qualification capture is optional, bounded, mode-0600, and intended only for a
short coordinated live format check. It is never sent to ANIMA or SENTRY.
"""

from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import hmac
import json
import os
import re
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

TAPO_PACKAGE = "com.tplink.iot"
WANSVIEW_PACKAGE = "net.ajcloud.wansviewplus"
ALLOWED_PACKAGES = frozenset({TAPO_PACKAGE, WANSVIEW_PACKAGE})
MAX_CONFIG_BYTES = 32_768
MAX_TEXT = 512


class RelayConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Rule:
    package_name: str
    resource_alias: str
    kind: str
    alias_terms: tuple[str, ...]
    event_terms: tuple[str, ...]
    profile_after: str | None = None
    reported_method: str | None = None


@dataclass(frozen=True, slots=True)
class Config:
    endpoint: str
    token_file: Path
    status_file: Path
    capture_file: Path | None
    capture_limit: int
    capture_packages: frozenset[str]
    rules: tuple[Rule, ...]


def _private_regular(path: Path, *, maximum: int) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_uid != os.geteuid()
            or info.st_size > maximum
        ):
            raise RelayConfigurationError("unsafe private file")
        raw = os.read(descriptor, maximum + 1)
        if len(raw) > maximum:
            raise RelayConfigurationError("private file exceeds bound")
        return raw
    finally:
        os.close(descriptor)


def _label(value: Any, *, limit: int = 64) -> str:
    if not isinstance(value, str) or not re.fullmatch(rf"[A-Za-z0-9_.-]{{1,{limit}}}", value):
        raise RelayConfigurationError("invalid bounded label")
    return value


def load_config(path: Path) -> Config:
    try:
        data = json.loads(_private_regular(path, maximum=MAX_CONFIG_BYTES))
        required_keys = {
            "version",
            "endpoint",
            "token_file",
            "status_file",
            "capture_file",
            "capture_limit",
            "rules",
        }
        keys = set(data) if isinstance(data, dict) else set()
        if not isinstance(data, dict) or keys not in (
            required_keys,
            required_keys | {"capture_packages"},
        ):
            raise RelayConfigurationError("invalid configuration keys")
        if data["version"] != 1 or not isinstance(data["rules"], list):
            raise RelayConfigurationError("invalid configuration version")
        endpoint = urllib.parse.urlparse(data["endpoint"])
        if (
            endpoint.scheme != "http"
            or endpoint.hostname not in {"127.0.0.1", "localhost"}
            or endpoint.path.rstrip("/") != "/api/v1/vendor-events/receive"
            or endpoint.query
            or endpoint.fragment
        ):
            raise RelayConfigurationError("endpoint must be the loopback ANIMA receiver")
        token_file = Path(data["token_file"])
        status_file = Path(data["status_file"])
        capture_file = Path(data["capture_file"]) if data["capture_file"] else None
        if not token_file.is_absolute() or not status_file.is_absolute():
            raise RelayConfigurationError("runtime paths must be absolute")
        if capture_file is not None and (
            not capture_file.is_absolute() or not str(capture_file).startswith("/run/user/")
        ):
            raise RelayConfigurationError("qualification capture must use volatile user runtime")
        capture_limit = data["capture_limit"]
        if type(capture_limit) is not int or not 0 <= capture_limit <= 16:
            raise RelayConfigurationError("invalid capture limit")
        capture_packages = frozenset(data.get("capture_packages", ALLOWED_PACKAGES))
        if capture_packages - ALLOWED_PACKAGES or any(
            not isinstance(value, str) for value in data.get("capture_packages", [])
        ):
            raise RelayConfigurationError("invalid capture packages")
        rules: list[Rule] = []
        for item in data["rules"]:
            if not isinstance(item, dict) or set(item) != {
                "package_name",
                "resource_alias",
                "kind",
                "alias_terms",
                "event_terms",
                "profile_after",
                "reported_method",
            }:
                raise RelayConfigurationError("invalid rule keys")
            package = str(item["package_name"])
            if package not in ALLOWED_PACKAGES:
                raise RelayConfigurationError("unsupported package")
            alias = _label(item["resource_alias"])
            kind = _label(item["kind"])
            if package == WANSVIEW_PACKAGE and kind != "motion_reported":
                raise RelayConfigurationError("invalid Wansview event kind")
            if package == TAPO_PACKAGE and kind not in {"locked", "unlocked"}:
                raise RelayConfigurationError("invalid Tapo event kind")
            alias_terms = tuple(str(value).casefold() for value in item["alias_terms"])
            event_terms = tuple(str(value).casefold() for value in item["event_terms"])
            if (
                not 1 <= len(alias_terms) <= 8
                or not 1 <= len(event_terms) <= 8
                or any(not value or len(value) > 80 for value in alias_terms + event_terms)
            ):
                raise RelayConfigurationError("invalid rule terms")
            profile_after = item["profile_after"]
            method = item["reported_method"]
            if profile_after is not None and (
                not isinstance(profile_after, str) or not 1 <= len(profile_after) <= 40
            ):
                raise RelayConfigurationError("invalid profile boundary")
            if method is not None:
                method = _label(method, limit=40)
            rules.append(
                Rule(package, alias, kind, alias_terms, event_terms, profile_after, method)
            )
        if len(rules) > 64:
            raise RelayConfigurationError("too many rules")
        _private_regular(token_file, maximum=512)
        return Config(
            data["endpoint"],
            token_file,
            status_file,
            capture_file,
            capture_limit,
            capture_packages,
            tuple(rules),
        )
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        if isinstance(exc, RelayConfigurationError):
            raise
        raise RelayConfigurationError("invalid relay configuration") from None


def _bounded(value: Any) -> str:
    return " ".join(str(value).split())[:MAX_TEXT]


def _vendor_token(master: str, package_name: str) -> str:
    """Derive one revocable receiver identity per official package."""
    digest = hmac.new(master.encode(), package_name.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def match_report(
    package_name: str,
    summary: Any,
    body: Any,
    rules: tuple[Rule, ...],
    *,
    received_at: datetime,
) -> dict[str, Any] | None:
    """Return only a minimized typed report; unknown messages are discarded."""
    if package_name not in ALLOWED_PACKAGES:
        return None
    text = f"{_bounded(summary)} {_bounded(body)}".casefold()
    for rule in rules:
        if (
            rule.package_name != package_name
            or not any(term in text for term in rule.alias_terms)
            or not any(term in text for term in rule.event_terms)
        ):
            continue
        now = received_at.astimezone(UTC).isoformat()
        if package_name == WANSVIEW_PACKAGE:
            fields: dict[str, Any] = {
                "format": "anima.android.motion.report.v1",
                "delivery_id": str(uuid4()),
                "camera_alias": rule.resource_alias,
                "channel_id": None,
                "kind": "motion_reported",
                "android_posted_at": None,
                "source_occurred_at": None,
                "relay_received_at": now,
                "is_group_summary": None,
                "reported_loss_count": None,
            }
        else:
            profile = None
            if rule.profile_after:
                marker = rule.profile_after.casefold()
                offset = text.find(marker)
                if offset >= 0:
                    candidate = _bounded(text[offset + len(marker) :]).strip(" .,:;!-")
                    profile = candidate[:80] or None
            fields = {
                "format": "anima.android.lock.report.v1",
                "delivery_id": str(uuid4()),
                "resource_alias": rule.resource_alias,
                "kind": rule.kind,
                "reported_profile_ref": profile,
                "reported_method": rule.reported_method,
                "source_occurred_at": None,
                "relay_received_at": now,
            }
        return {"package_name": package_name, "fields": fields}
    return None


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


class Relay:
    def __init__(self, config: Config, *, clock: Callable[[], float] = time.time) -> None:
        self.config = config
        self.clock = clock
        # Reuse the existing private atomic JSON snapshot facility, not a new
        # database platform. Persistent minimized outbox is separate from the
        # volatile heartbeat AND from credentials, beside the private token.
        self.outbox_path = config.token_file.with_name("vendor-relay-outbox.json")
        self._directory = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        for part in self.outbox_path.parent.parts[1:]:
            following = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self._directory
            )
            os.close(self._directory)
            self._directory = following
        info = os.fstat(self._directory)
        if info.st_uid != os.geteuid() or info.st_mode & 0o022:
            os.close(self._directory)
            raise RelayConfigurationError("unsafe outbox directory")
        self._lock_fd = os.open(
            "vendor-relay-outbox.lock",
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
            0o600,
            dir_fd=self._directory,
        )
        info = os.fstat(self._lock_fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
        ):
            self.close()
            raise RelayConfigurationError("unsafe outbox lock")
        try:
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                fd = os.open(
                    self.outbox_path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=self._directory
                )
            except FileNotFoundError:
                self.outbox: list[dict[str, Any]] = []
                self.overflow_count = 0
            else:
                with os.fdopen(fd, "r", encoding="utf-8") as stream:
                    info = os.fstat(stream.fileno())
                    if (
                        not stat.S_ISREG(info.st_mode)
                        or stat.S_IMODE(info.st_mode) != 0o600
                        or info.st_uid != os.geteuid()
                        or info.st_nlink != 1
                        or info.st_size > 65536
                    ):
                        raise RelayConfigurationError("unsafe outbox snapshot")
                    value = json.load(stream)
                if (
                    not isinstance(value, dict)
                    or value.get("version") != 1
                    or not isinstance(value.get("deliveries"), list)
                    or len(value["deliveries"]) > 80
                ):
                    raise RelayConfigurationError("invalid outbox snapshot")
                self.outbox = value["deliveries"]
                self.overflow_count = value.get("overflow_count", 0)
                if type(self.overflow_count) is not int or self.overflow_count < 0:
                    raise RelayConfigurationError("invalid outbox snapshot")
                for item in self.outbox:
                    self._validate_delivery(item)
        except Exception:
            self.close()
            raise
        # Bus IDs and occurrence UUIDs have separate lifetimes. The epoch is
        # metadata only; no upstream immutable occurrence key/time is available.
        self.epoch = str(uuid4())
        self._next_id = 1
        self._notifications: set[int] = set()
        self.capture_count = 0
        self.received = 0
        self.accepted = 0
        self.rejected = 0
        self.failed = 0
        self.received_by_package: dict[str, int] = {}
        self.accepted_by_package: dict[str, int] = {}

    def close(self) -> None:
        for attribute in ("_lock_fd", "_directory"):
            fd = getattr(self, attribute, None)
            if fd is not None:
                os.close(fd)
                setattr(self, attribute, None)

    def _persist(self) -> None:
        # Directory descriptor pins the validated directory through replace;
        # neither an attacker symlink nor a sidefile is followed/created.
        encoded = json.dumps(
            {"version": 1, "deliveries": self.outbox, "overflow_count": self.overflow_count},
            sort_keys=True,
        ).encode()
        if len(encoded) > 65536:
            raise RelayConfigurationError("outbox snapshot capacity exhausted")
        temporary = f".outbox-{uuid4()}.tmp"
        fd = os.open(
            temporary,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
            0o600,
            dir_fd=self._directory,
        )
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.rename(
                temporary,
                self.outbox_path.name,
                src_dir_fd=self._directory,
                dst_dir_fd=self._directory,
            )
            os.fsync(self._directory)
        finally:
            try:
                os.unlink(temporary, dir_fd=self._directory)
            except FileNotFoundError:
                pass

    def _status(self, state: str, package_name: str | None = None) -> None:
        counts: dict[str, int] = {}
        for item in self.outbox:
            counts[item["state"]] = counts.get(item["state"], 0) + 1
        pending = counts.get("PENDING", 0)
        failed = counts.get("ESCALATED", 0) + counts.get("UNKNOWN", 0) + self.overflow_count
        _atomic_json(
            self.config.status_file,
            {
                "version": 1,
                "state": state,
                "transport_state": "LISTENING",
                "bus_epoch": self.epoch,
                "delivery_state": "FAULT" if failed else "PENDING" if pending else "CURRENT",
                "pending_obligations": pending,
                "escalated_obligations": failed,
                "overflow_count": self.overflow_count,
                "observed_at": datetime.now(UTC).isoformat(),
                "last_package": package_name,
                "received": self.received,
                "accepted": self.accepted,
                "rejected": self.rejected,
                "failed": self.failed,
                "received_by_package": dict(sorted(self.received_by_package.items())),
                "accepted_by_package": dict(sorted(self.accepted_by_package.items())),
                "qualification_captures": self.capture_count,
            },
        )

    def _capture(self, package_name: str, summary: Any, body: Any) -> None:
        if (
            self.config.capture_file is None
            or package_name not in self.config.capture_packages
            or self.capture_count >= self.config.capture_limit
        ):
            return
        path = self.config.capture_file
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
                raise RelayConfigurationError("unsafe capture file")
            record = {
                "package_name": package_name,
                "summary": _bounded(summary),
                "body": _bounded(body),
                "received_at": datetime.now(UTC).isoformat(),
            }
            os.write(descriptor, (json.dumps(record) + "\n").encode())
            self.capture_count += 1
        finally:
            os.close(descriptor)

    def receive(self, package_name: str, summary: Any, body: Any) -> str | None:
        # Package identity comes from Waydroid's server-owned desktop-entry hint.
        # Return before reading text for every other Android package.
        if package_name not in ALLOWED_PACKAGES:
            return
        self.received += 1
        self.received_by_package[package_name] = self.received_by_package.get(package_name, 0) + 1
        self._capture(package_name, summary, body)
        report = match_report(
            package_name, summary, body, self.config.rules, received_at=datetime.now(UTC)
        )
        if report is None:
            self.rejected += 1
            self._status("UNRECOGNIZED_FORMAT", package_name)
            return
        delivery_id = report["fields"]["delivery_id"]
        at = self.clock()
        self._compact_receipts(at)
        if sum(item["state"] != "ACKNOWLEDGED" for item in self.outbox) >= 64:
            self.overflow_count += 1
            self._persist()
            self._status("OUTBOX_CAPACITY_EXHAUSTED", package_name)
            raise RelayConfigurationError("outbox capacity exhausted")
        self.outbox.append(
            {
                "delivery_id": delivery_id,
                "package": package_name,
                "report": report,
                "created": at,
                "due": at,
                "attempts": 0,
                "state": "PENDING",
                "transport_attempted": False,
            }
        )
        self._persist()  # Persist before transport/Notify acknowledgement.
        self.drain()
        return str(delivery_id)

    def notify(self, package_name: str, replaces_id: int, summary: Any, body: Any) -> int:
        # Every callback is distinct, even a same-text replacement. Upstream
        # does not supply an immutable event key; cross-callback dedup UNKNOWN.
        self.receive(package_name, summary, body)
        assigned = replaces_id if replaces_id else self._next_id
        self._next_id = max(self._next_id, assigned + 1)
        self._notifications.add(assigned)
        return assigned

    def close_notification(self, notification_id: int) -> None:
        if notification_id not in self._notifications:
            raise ValueError("unknown notification ID")
        self._notifications.remove(notification_id)

    def _compact_receipts(self, at: float) -> None:
        acknowledged = [
            item
            for item in self.outbox
            if item["state"] == "ACKNOWLEDGED" and item["created"] >= at - 86400
        ][-16:]
        # Unresolved/uncertain obligations are NEVER displaced by receipt history.
        self.outbox = [
            item for item in self.outbox if item["state"] != "ACKNOWLEDGED"
        ] + acknowledged

    @staticmethod
    def _validate_delivery(item: Any) -> None:
        if (
            not isinstance(item, dict)
            or item.get("package") not in ALLOWED_PACKAGES
            or item.get("state") not in {"PENDING", "ACKNOWLEDGED", "UNKNOWN", "ESCALATED"}
            or type(item.get("attempts")) is not int
            or item["attempts"] < 0
            or type(item.get("transport_attempted")) is not bool
            or any(type(item.get(key)) not in {int, float} for key in ("created", "due"))
            or not isinstance(item.get("delivery_id"), str)
        ):
            raise RelayConfigurationError("invalid outbox delivery")
        from uuid import UUID

        UUID(item["delivery_id"])
        report = item.get("report")
        if item["state"] != "PENDING":
            if report is not None:
                raise RelayConfigurationError("unexpected retained report")
            return
        expected = (
            {
                "format",
                "delivery_id",
                "camera_alias",
                "channel_id",
                "kind",
                "android_posted_at",
                "source_occurred_at",
                "relay_received_at",
                "is_group_summary",
                "reported_loss_count",
            }
            if item["package"] == WANSVIEW_PACKAGE
            else {
                "format",
                "delivery_id",
                "resource_alias",
                "kind",
                "reported_profile_ref",
                "reported_method",
                "source_occurred_at",
                "relay_received_at",
            }
        )
        if (
            not isinstance(report, dict)
            or set(report) != {"package_name", "fields"}
            or report["package_name"] != item["package"]
            or not isinstance(report["fields"], dict)
            or set(report["fields"]) != expected
            or report["fields"].get("delivery_id") != item["delivery_id"]
            or any(
                value is not None and not isinstance(value, (str, bool, int))
                for value in report["fields"].values()
            )
            or any(
                isinstance(value, str) and len(value) > 100 for value in report["fields"].values()
            )
        ):
            raise RelayConfigurationError("invalid minimized outbox report")

    def drain(self) -> None:
        at = self.clock()
        # An attempted POST can have committed Journal/handoff despite a lost
        # receipt. Expiration never relabels that uncertainty as clearly unsent.
        for item in self.outbox:
            if item["state"] == "PENDING" and item["created"] < at - 3600:
                item.update(
                    state="UNKNOWN" if item["transport_attempted"] else "ESCALATED",
                    report=None,
                    receipt="EXPIRED_UNACKNOWLEDGED",
                )
        row = next(
            (item for item in self.outbox if item["state"] == "PENDING" and item["due"] <= at), None
        )
        self._persist()
        if row is None:
            self._status("READY")
            return
        package_name = row["package"]
        master = _private_regular(self.config.token_file, maximum=512).decode().strip()
        token = _vendor_token(master, package_name)
        request = urllib.request.Request(
            self.config.endpoint,
            data=json.dumps(row["report"], separators=(",", ":")).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        row["transport_attempted"] = True
        self._persist()
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                if response.status != 200:
                    raise urllib.error.HTTPError(
                        self.config.endpoint, response.status, "receiver rejected report", {}, None
                    )
                receipt = json.loads(response.read(4096))
                if (
                    receipt.get("status") != "RECORDED"
                    or receipt.get("delivery_id") != row["delivery_id"]
                    or not isinstance(receipt.get("event_id"), str)
                    or type(receipt.get("journal_position")) is not int
                    or receipt.get("attention") not in {"QUEUED", "NO_NEW_REQUEST", "NOT_ELIGIBLE"}
                ):
                    raise ValueError("invalid durable receipt")
            row.update(
                state="ACKNOWLEDGED",
                report=None,
                receipt={
                    key: receipt[key] for key in ("event_id", "journal_position", "attention")
                },
            )
            self._compact_receipts(at)
            self._persist()
            self.accepted += 1
            self.accepted_by_package[package_name] = (
                self.accepted_by_package.get(package_name, 0) + 1
            )
            self._status("DELIVERED", package_name)
        except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError):
            attempts = row["attempts"] + 1
            row.update(attempts=attempts, due=at + min(300, 2 ** min(attempts, 9)))
            self._persist()
            self.failed += 1
            self._status("DELIVERY_FAILED", package_name)


def serve(config: Config) -> None:
    try:
        import dbus
        import dbus.service
        from dbus.mainloop.glib import DBusGMainLoop
        from gi.repository import GLib
    except ImportError as exc:
        raise SystemExit("system dbus-python and PyGObject are required") from exc

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    relay = Relay(config)

    class NotificationService(dbus.service.Object):
        def __init__(self) -> None:
            owner = dbus.service.BusName(
                "org.freedesktop.Notifications", bus=bus, do_not_queue=True
            )
            super().__init__(owner, "/org/freedesktop/Notifications")
            self._bus_name_owner = owner

        @dbus.service.method(
            "org.freedesktop.Notifications",
            in_signature="susssasa{sv}i",
            out_signature="u",
        )
        def Notify(
            self,
            app_name: Any,
            replaces_id: Any,
            app_icon: Any,
            summary: Any,
            body: Any,
            actions: Any,
            hints: Any,
            expire_timeout: Any,
        ) -> int:
            del app_name, app_icon, actions, expire_timeout
            desktop_entry = str(hints.get("desktop-entry", ""))
            prefix = "waydroid."
            if desktop_entry.startswith(prefix):
                desktop_entry = desktop_entry[len(prefix) :]
            return relay.notify(desktop_entry, int(replaces_id), summary, body)

        @dbus.service.method("org.freedesktop.Notifications", in_signature="u")
        def CloseNotification(self, notification_id: Any) -> None:
            try:
                relay.close_notification(int(notification_id))
            except ValueError as exc:
                raise dbus.exceptions.DBusException(str(exc)) from None
            self.NotificationClosed(int(notification_id), 3)

        @dbus.service.signal("org.freedesktop.Notifications", signature="uu")
        def NotificationClosed(self, notification_id: int, reason: int) -> None:
            del notification_id, reason

        @dbus.service.method("org.freedesktop.Notifications", out_signature="as")
        def GetCapabilities(self) -> list[str]:
            return []

        @dbus.service.method("org.freedesktop.Notifications", out_signature="ssss")
        def GetServerInformation(self) -> tuple[str, str, str, str]:
            return ("ANIMA private vendor relay", "ANIMA", "1", "1.2")

        @dbus.service.signal("org.freedesktop.Notifications", signature="us")
        def ActionInvoked(self, notification_id: int, action_key: str) -> None:
            del notification_id, action_key

        @dbus.service.signal("org.freedesktop.Notifications", signature="us")
        def ActivationToken(self, notification_id: int, token: str) -> None:
            del notification_id, token

    service = NotificationService()
    relay._status("READY")
    GLib.timeout_add_seconds(2, lambda: (relay.drain(), True)[1])
    try:
        GLib.MainLoop().run()
    finally:
        relay.close()
        del service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        serve(load_config(arguments.config))
    except RelayConfigurationError:
        print("vendor relay configuration rejected", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
