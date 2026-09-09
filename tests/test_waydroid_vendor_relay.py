"""Pure contract tests for the host-only Waydroid relay parser."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def relay_module() -> Any:
    path = Path(__file__).parents[1] / "scripts" / "waydroid_vendor_relay.py"
    spec = importlib.util.spec_from_file_location("waydroid_vendor_relay", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def rules(module: Any) -> tuple[Any, ...]:
    return (
        module.Rule(
            module.WANSVIEW_PACKAGE,
            "back-yard",
            "motion_reported",
            ("back yard",),
            ("new motion alert from back yard",),
        ),
        module.Rule(
            module.TAPO_PACKAGE,
            "front-door",
            "unlocked",
            ("front door",),
            ("unlocked",),
            "unlocked by ",
            "fingerprint",
        ),
    )


def test_rejects_other_package_before_reading_message() -> None:
    module = relay_module()

    class Explodes:
        def __str__(self) -> str:
            raise AssertionError("unrelated notification text was read")

    assert (
        module.match_report(
            "unrelated.application",
            Explodes(),
            Explodes(),
            rules(module),
            received_at=datetime(2026, 9, 7, tzinfo=UTC),
        )
        is None
    )


def test_wansview_motion_becomes_minimized_report() -> None:
    module = relay_module()
    report = module.match_report(
        module.WANSVIEW_PACKAGE,
        "Motion alert",
        "New motion alert from Back Yard",
        rules(module),
        received_at=datetime(2026, 9, 7, tzinfo=UTC),
    )
    assert report is not None
    assert report["package_name"] == module.WANSVIEW_PACKAGE
    assert report["fields"]["camera_alias"] == "back-yard"
    assert report["fields"]["kind"] == "motion_reported"
    assert set(report["fields"]) == {
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


def test_wansview_non_motion_notice_is_not_forwarded() -> None:
    module = relay_module()
    assert (
        module.match_report(
            module.WANSVIEW_PACKAGE,
            "Wansview Cloud",
            "Camera Back Yard is connected",
            rules(module),
            received_at=datetime(2026, 9, 7, tzinfo=UTC),
        )
        is None
    )


def test_tapo_unlock_preserves_only_bounded_reported_profile() -> None:
    module = relay_module()
    report = module.match_report(
        module.TAPO_PACKAGE,
        "Front Door",
        "Unlocked by Owner",
        rules(module),
        received_at=datetime(2026, 9, 7, tzinfo=UTC),
    )
    assert report is not None
    assert report["fields"]["resource_alias"] == "front-door"
    assert report["fields"]["kind"] == "unlocked"
    assert report["fields"]["reported_profile_ref"] == "owner"
    assert "Front Door" not in repr(report)


def test_unknown_same_app_notice_is_not_forwarded() -> None:
    module = relay_module()
    assert (
        module.match_report(
            module.TAPO_PACKAGE,
            "Account",
            "Verification code 123456",
            rules(module),
            received_at=datetime(2026, 9, 7, tzinfo=UTC),
        )
        is None
    )


def test_capture_can_be_restricted_to_one_qualified_package(tmp_path: Path) -> None:
    module = relay_module()
    token = tmp_path / "token"
    token.write_text("x" * 40)
    token.chmod(0o600)
    capture = Path(f"/run/user/{os.getuid()}/anima-relay-test-{os.getpid()}.jsonl")
    config_file = tmp_path / "relay.json"
    config_file.write_text(
        json.dumps(
            {
                "version": 1,
                "endpoint": "http://127.0.0.1:18090/api/v1/vendor-events/receive",
                "token_file": str(token),
                "status_file": str(tmp_path / "status.json"),
                "capture_file": str(capture),
                "capture_limit": 2,
                "capture_packages": [module.WANSVIEW_PACKAGE],
                "rules": [],
            }
        )
    )
    config_file.chmod(0o600)
    try:
        relay = module.Relay(module.load_config(config_file))
        relay._capture(module.TAPO_PACKAGE, "Front Door", "was unlocked")
        assert not capture.exists()
        relay._capture(module.WANSVIEW_PACKAGE, "Back Yard", "motion")
        assert capture.exists()
        assert len(capture.read_text().splitlines()) == 1
    finally:
        capture.unlink(missing_ok=True)


def test_vendor_receiver_credentials_are_package_scoped() -> None:
    module = relay_module()
    master = "m" * 48
    tapo = module._vendor_token(master, module.TAPO_PACKAGE)
    wansview = module._vendor_token(master, module.WANSVIEW_PACKAGE)
    assert tapo != wansview
    assert len(tapo) == len(wansview) == 43
    assert master not in tapo and master not in wansview
