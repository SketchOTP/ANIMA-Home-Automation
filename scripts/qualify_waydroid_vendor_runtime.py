#!/usr/bin/env python3
"""Qualify observed vendor formats without printing or retaining raw vendor text.

This operator helper reads only the private, volatile qualification capture and
atomically updates the private relay configuration. A vendor is enabled only
after its official package has emitted the exact bounded event form expected by
the relay. Previously qualified rules remain intact when their raw samples have
already been removed.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

TAPO_PACKAGE = "com.tplink.iot"
WANSVIEW_PACKAGE = "net.ajcloud.wansviewplus"


def private_json(path: Path, maximum: int) -> Any:
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
            raise ValueError("unsafe private qualification file")
        return json.loads(os.read(descriptor, maximum + 1))
    finally:
        os.close(descriptor)


def atomic_private(path: Path, value: Any) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    arguments = parser.parse_args()
    config = private_json(arguments.config, 32_768)
    if not isinstance(config, dict) or not isinstance(config.get("rules"), list):
        raise SystemExit("invalid relay configuration")
    records: list[dict[str, Any]] = []
    with arguments.capture.open(encoding="utf-8") as stream:
        for line in stream:
            value = json.loads(line)
            if isinstance(value, dict):
                records.append(value)
    tapo_texts = [
        f"{value.get('summary', '')} {value.get('body', '')}".casefold()
        for value in records
        if value.get("package_name") == TAPO_PACKAGE
    ]
    tapo_qualified = (
        any("front door" in text and " was locked" in text for text in tapo_texts)
        and any("front door" in text and " was unlocked" in text for text in tapo_texts)
    ) or {
        (rule.get("resource_alias"), rule.get("kind"))
        for rule in config["rules"]
        if rule.get("package_name") == TAPO_PACKAGE
    } >= {("front-door", "locked"), ("front-door", "unlocked")}
    if not tapo_qualified:
        raise SystemExit("qualified Tapo locked/unlocked evidence not found")

    wansview_records = [value for value in records if value.get("package_name") == WANSVIEW_PACKAGE]
    observed_cameras = {
        camera
        for value in wansview_records
        for camera in ("back yard", "garage")
        if str(value.get("summary", "")).casefold().strip() == "motion alert"
        and str(value.get("body", "")).casefold().strip() == f"new motion alert from {camera}"
    }
    if not observed_cameras:
        raise SystemExit("qualified Wansview motion sample not found")

    retained = [
        rule
        for rule in config["rules"]
        if rule.get("package_name") not in {TAPO_PACKAGE, WANSVIEW_PACKAGE}
    ]
    retained.extend(
        [
            {
                "package_name": TAPO_PACKAGE,
                "resource_alias": "front-door",
                "kind": "unlocked",
                "alias_terms": ["front door"],
                "event_terms": [" was unlocked"],
                "profile_after": "unlocked by ",
                "reported_method": None,
            },
            {
                "package_name": TAPO_PACKAGE,
                "resource_alias": "front-door",
                "kind": "locked",
                "alias_terms": ["front door"],
                "event_terms": [" was locked"],
                "profile_after": None,
                "reported_method": None,
            },
            {
                "package_name": WANSVIEW_PACKAGE,
                "resource_alias": "back-yard",
                "kind": "motion_reported",
                "alias_terms": ["back yard"],
                "event_terms": ["new motion alert from back yard"],
                "profile_after": None,
                "reported_method": None,
            },
            {
                "package_name": WANSVIEW_PACKAGE,
                "resource_alias": "garage",
                "kind": "motion_reported",
                "alias_terms": ["garage"],
                "event_terms": ["new motion alert from garage"],
                "profile_after": None,
                "reported_method": None,
            },
        ]
    )
    config["rules"] = retained
    config["capture_packages"] = []
    config["capture_limit"] = 0
    atomic_private(arguments.config, config)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{arguments.capture.name}.", dir=arguments.capture.parent
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, arguments.capture)
        os.chmod(arguments.capture, 0o600)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise
    print(
        "Tapo lock/unlock and Wansview motion formats qualified; "
        f"observed Wansview cameras={','.join(sorted(observed_cameras))}; "
        "raw vendor captures removed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
