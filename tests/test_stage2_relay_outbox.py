"""Isolated producer fixtures: no Android bus, credential or owner endpoint."""

from __future__ import annotations

import json
import shutil
import urllib.error
from pathlib import Path
from typing import Any

import pytest
from test_waydroid_vendor_relay import relay_module, rules


class Receipt:
    status = 200

    def __init__(self, report: dict[str, Any]) -> None:
        self.report = report

    def __enter__(self) -> Receipt:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def read(self, size: int) -> bytes:
        return json.dumps(
            {
                "status": "RECORDED",
                "delivery_id": self.report["fields"]["delivery_id"],
                "event_id": "isolated-event",
                "journal_position": 1,
                "attention": "QUEUED",
            }
        ).encode()


def configuration(module: Any, root: Path) -> Any:
    persistent = root / "persistent"
    persistent.mkdir(mode=0o700, exist_ok=True)
    token = persistent / "relay.token"
    token.write_text("isolated-test-secret")
    token.chmod(0o600)
    return module.Config(
        "http://127.0.0.1/isolated",
        token,
        root / "volatile" / "status.json",
        None,
        0,
        frozenset(),
        rules(module),
    )


def test_replacements_distinct_same_text_ids_and_receipt_compaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = relay_module()
    reports: list[dict[str, Any]] = []

    def post(request: Any, **kwargs: Any) -> Receipt:
        report = json.loads(request.data)
        reports.append(report)
        return Receipt(report)

    monkeypatch.setattr(module.urllib.request, "urlopen", post)
    relay = module.Relay(configuration(module, tmp_path))
    try:
        unknown = relay.notify("unknown.package", 0, "ignored", "ignored")
        identifier = relay.notify(
            module.WANSVIEW_PACKAGE, 0, "Motion", "New motion alert from Back Yard"
        )
        assert identifier != unknown
        for _ in range(100):
            assert (
                relay.notify(
                    module.WANSVIEW_PACKAGE, identifier, "Motion", "New motion alert from Back Yard"
                )
                == identifier
            )
        assert len(reports) == 101
        assert len({report["fields"]["delivery_id"] for report in reports}) == 101
        assert len(relay.outbox) <= 16
        assert all(item["state"] == "ACKNOWLEDGED" for item in relay.outbox)
        relay.close_notification(identifier)
        with pytest.raises(ValueError, match="unknown notification"):
            relay.close_notification(identifier)
        new_id = relay.notify(
            module.WANSVIEW_PACKAGE, 0, "Motion", "New motion alert from Back Yard"
        )
        assert new_id not in {identifier, unknown}
    finally:
        relay.close()


def test_changed_lock_replacement_is_a_new_occurrence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = relay_module()
    cfg = configuration(module, tmp_path)
    from dataclasses import replace

    cfg = replace(
        cfg,
        rules=(
            *cfg.rules,
            module.Rule(
                module.TAPO_PACKAGE, "front-door", "locked", ("front door",), ("now locked",)
            ),
        ),
    )
    reports: list[dict[str, Any]] = []

    def post(request: Any, **kwargs: Any) -> Receipt:
        report = json.loads(request.data)
        reports.append(report)
        return Receipt(report)

    monkeypatch.setattr(module.urllib.request, "urlopen", post)
    relay = module.Relay(cfg)
    try:
        identifier = relay.notify(module.TAPO_PACKAGE, 0, "Front Door", "unlocked")
        assert (
            relay.notify(module.TAPO_PACKAGE, identifier, "Front Door", "now locked") == identifier
        )
        assert [item["fields"]["kind"] for item in reports] == ["unlocked", "locked"]
        assert reports[0]["fields"]["delivery_id"] != reports[1]["fields"]["delivery_id"]
    finally:
        relay.close()


def test_retry_survives_volatile_deletion_and_epoch_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = relay_module()
    cfg = configuration(module, tmp_path)
    clock = [1_000.0]
    reports: list[dict[str, Any]] = []

    def failed(request: Any, **kwargs: Any) -> Receipt:
        reports.append(json.loads(request.data))
        raise urllib.error.URLError("isolated uncertain transport")

    monkeypatch.setattr(module.urllib.request, "urlopen", failed)
    first = module.Relay(cfg, clock=lambda: clock[0])
    first.notify(module.WANSVIEW_PACKAGE, 0, "Motion", "New motion alert from Back Yard")
    old_epoch = first.epoch
    first.close()
    shutil.rmtree(tmp_path / "volatile")  # Only the isolated runtime fixture.
    second = module.Relay(cfg, clock=lambda: clock[0])
    try:
        assert second.epoch != old_epoch
        assert second.outbox_path.parent == tmp_path / "persistent"
        assert second.outbox_path.stat().st_mode & 0o777 == 0o600
        clock[0] += 3

        def accepted(request: Any, **kwargs: Any) -> Receipt:
            report = json.loads(request.data)
            reports.append(report)
            return Receipt(report)

        monkeypatch.setattr(module.urllib.request, "urlopen", accepted)
        second.drain()
        assert reports[0] == reports[1]  # Immutable exact transport retry.
        second.notify(module.WANSVIEW_PACKAGE, 1, "Motion", "New motion alert from Back Yard")
        assert reports[2]["fields"]["delivery_id"] != reports[1]["fields"]["delivery_id"]
        assert "New motion alert" not in second.outbox_path.read_text()
        assert "isolated-test-secret" not in second.outbox_path.read_text()
    finally:
        second.close()


def test_unknown_expiration_overflow_and_single_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = relay_module()
    cfg = configuration(module, tmp_path)
    clock = [1_000.0]

    def failed(*args: Any, **kwargs: Any) -> None:
        raise urllib.error.URLError("isolated lost receipt")

    monkeypatch.setattr(module.urllib.request, "urlopen", failed)
    relay = module.Relay(cfg, clock=lambda: clock[0])
    try:
        with pytest.raises(BlockingIOError):
            module.Relay(cfg)
        drain = relay.drain
        monkeypatch.setattr(relay, "drain", lambda: None)
        relay.notify(module.WANSVIEW_PACKAGE, 0, "Motion", "New motion alert from Back Yard")
        monkeypatch.setattr(relay, "drain", drain)
        # Leave one durably queued report explicitly unattempted while others
        # simulate lost receipts; both expiration classes must remain truthful.
        relay.outbox[0]["due"] = clock[0] + 4000
        for _ in range(63):
            relay.notify(module.WANSVIEW_PACKAGE, 0, "Motion", "New motion alert from Back Yard")
        identities = {item["delivery_id"] for item in relay.outbox}
        with pytest.raises(module.RelayConfigurationError, match="capacity"):
            relay.notify(module.WANSVIEW_PACKAGE, 0, "Motion", "New motion alert from Back Yard")
        assert identities == {item["delivery_id"] for item in relay.outbox}
        status = json.loads(cfg.status_file.read_text())
        assert status["delivery_state"] == "FAULT" and status["overflow_count"] == 1
        clock[0] += 3601
        relay.drain()
        assert relay.outbox[0]["state"] == "ESCALATED"
        assert any(item["state"] == "UNKNOWN" for item in relay.outbox[1:])
        assert all(item["report"] is None for item in relay.outbox)
    finally:
        relay.close()


@pytest.mark.parametrize("target", ["parent", "snapshot", "lock"])
def test_outbox_does_not_follow_symlinks(tmp_path: Path, target: str) -> None:
    module = relay_module()
    cfg = configuration(module, tmp_path)
    destination = tmp_path / "other"
    destination.mkdir(mode=0o700)
    if target == "parent":
        alias = tmp_path / "alias"
        alias.symlink_to(cfg.token_file.parent, target_is_directory=True)
        from dataclasses import replace

        cfg = replace(cfg, token_file=alias / cfg.token_file.name)
    else:
        name = "vendor-relay-outbox.json" if target == "snapshot" else "vendor-relay-outbox.lock"
        (cfg.token_file.parent / name).symlink_to(destination / "untouched")
    with pytest.raises(OSError):
        module.Relay(cfg)
    assert not (destination / "untouched").exists()
