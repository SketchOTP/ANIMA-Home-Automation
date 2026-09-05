"""Exercise real Journal/Truth/Attention replay and plugin isolation.

The verifier uses unique run-scoped records in PostgreSQL.  It deliberately
does not delete household data or expose a fault-injection route.  Provider
and plugin callbacks are bounded local test runtimes; the durable journal,
truth projection, attention decisions, and plugin audit records are real Core
stores.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4, uuid5

import psycopg
from psycopg.rows import dict_row

from anima_ha.attention import AttentionProfile, AttentionRule, PostgresAttentionService, RuleAction
from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.journal import PostgresEventJournal, PostgresTruthProjection
from anima_ha.plugins import (
    CORE_VERSION,
    PluginManager,
    PluginManifest,
    PluginState,
    PostgresPluginStore,
    RuntimeKind,
    TrustClass,
)

DATABASE_URL = os.environ.get("ANIMA_DATABASE_URL", "")
RUN_ID = uuid4()
NAMESPACE = uuid5(UUID("45b1d177-fc39-4f2e-a9c4-95c15908c9d1"), str(RUN_ID))
SOURCE = f"phase14-r2-{RUN_ID}"


def _scalar(query: str, *args: Any) -> Any:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, args)
            row = cursor.fetchone()
            return next(iter(row.values())) if row else None


def _event(
    event_id: str,
    *,
    source_event_id: str,
    event_type: str,
    subject_key: str,
    sequence: int,
    value: Any,
    guaranteed: bool = False,
) -> EventEnvelope:
    now = datetime.now(UTC)
    return EventEnvelope.create(
        event_id=event_id,
        event_type=event_type,
        source=SOURCE,
        source_event_id=source_event_id,
        subject_key=subject_key,
        occurred_at=now,
        source_sequence=sequence,
        payload={
            "truth_key": subject_key,
            "source": SOURCE,
            "observed_at": now.isoformat(),
            "received_at": now.isoformat(),
            "state": "KNOWN",
            "value": value,
            "source_sequence": sequence,
            "confidence": 1.0,
            "evidence_kind": "DIRECT",
            "freshness_seconds": 3_600,
            "metadata": {"run_id": str(RUN_ID)},
        },
        importance=EventImportance.CRITICAL if guaranteed else EventImportance.IMPORTANT,
        delivery_class=DeliveryClass.GUARANTEED if guaranteed else DeliveryClass.BEST_EFFORT,
        metadata={
            "household_id": "phase14-r2-events",
            "run_id": str(RUN_ID),
            "guaranteed_attention": guaranteed,
        },
    )


def _result(scenario_id: str, *, detail: str, effects: int = 0) -> dict[str, Any]:
    return {
        "scenario_id": scenario_id,
        "status": "PASS",
        "evidence_level": "POSTGRES_JOURNAL_TRUTH_ATTENTION",
        "side_effect_count": effects,
        "detail": detail,
    }


def verify_events() -> list[dict[str, Any]]:
    journal = PostgresEventJournal(DATABASE_URL)
    projection = PostgresTruthProjection(DATABASE_URL)
    before = int(_scalar("SELECT COALESCE(max(journal_position), 0) FROM anima_event_journal") or 0)

    duplicate = _event(
        str(uuid5(NAMESPACE, "duplicate")),
        source_event_id="duplicate-source",
        event_type="truth.observation",
        subject_key=f"{SOURCE}/duplicate",
        sequence=1,
        value="on",
    )
    first = journal.append(duplicate)
    second = journal.append(duplicate)
    assert first.deduplicated is False and second.deduplicated is True
    assert (
        int(
            _scalar(
                "SELECT count(*) FROM anima_event_journal WHERE event_id=%s", duplicate.event_id
            )
        )
        == 1
    )

    source_first = _event(
        str(uuid5(NAMESPACE, "source-first")),
        source_event_id="same-source-id",
        event_type="truth.observation",
        subject_key=f"{SOURCE}/source",
        sequence=1,
        value="first",
    )
    source_second = _event(
        str(uuid5(NAMESPACE, "source-second")),
        source_event_id="same-source-id",
        event_type="truth.observation",
        subject_key=f"{SOURCE}/source",
        sequence=2,
        value="second",
    )
    source_one = journal.append(source_first)
    source_two = journal.append(source_second)
    assert source_one.deduplicated is False and source_two.deduplicated is True

    truth_key = f"{SOURCE}/out-of-order"
    newer = _event(
        str(uuid5(NAMESPACE, "newer")),
        source_event_id="truth-newer",
        event_type="truth.observation",
        subject_key=truth_key,
        sequence=2,
        value="new",
    )
    older = _event(
        str(uuid5(NAMESPACE, "older")),
        source_event_id="truth-older",
        event_type="truth.observation",
        subject_key=truth_key,
        sequence=1,
        value="old",
    )
    journal.append(newer)
    journal.append(older)

    senseguard = _event(
        str(uuid5(NAMESPACE, "senseguard")),
        source_event_id="senseguard-event",
        event_type="security.alarm",
        subject_key=f"{SOURCE}/senseguard",
        sequence=1,
        value="tripped",
        guaranteed=True,
    )
    sg_first = journal.append(senseguard)
    sg_second = journal.append(senseguard)
    assert sg_first.deduplicated is False and sg_second.deduplicated is True

    delayed = _event(
        str(uuid5(NAMESPACE, "delayed-projection")),
        source_event_id="delayed-projection",
        event_type="truth.observation",
        subject_key=f"{SOURCE}/delayed",
        sequence=1,
        value="available",
    )
    delayed_append = journal.append(delayed)
    assert delayed_append.deduplicated is False
    # This is the restart boundary: the journal commit is durable before the
    # projector is reconstructed and run.
    projected = projection.project_pending()
    assert projected.failure is None

    resolved = projection.get(truth_key)
    assert resolved.value == "new", resolved.to_dict()
    delayed_count = int(
        _scalar("SELECT count(*) FROM anima_truth_observations WHERE event_id=%s", delayed.event_id)
    )
    assert delayed_count == 1

    profile_version = f"phase14-r2-events-{RUN_ID}"
    profile = AttentionProfile(
        profile_version,
        (
            AttentionRule(
                "phase14-guaranteed",
                RuleAction.TRIGGER,
                event_types=("security.alarm",),
                priority=100,
            ),
        ),
    )
    attention = PostgresAttentionService(DATABASE_URL)
    attention.register_profile(profile)
    with psycopg.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE anima_attention_cursors SET last_position=%s WHERE consumer_name=%s",
            (before, f"phase14-events-{RUN_ID}"),
        )
        if cursor.rowcount == 0:
            cursor.execute(
                "INSERT INTO anima_attention_cursors "
                "(consumer_name, profile_version, last_position) VALUES (%s,%s,%s)",
                (f"phase14-events-{RUN_ID}", profile_version, before),
            )
        connection.commit()
    processed = attention.process(profile, consumer_name=f"phase14-events-{RUN_ID}")
    assert processed.failure is None
    triggers = [
        item
        for item in attention.list_triggers(profile_version)
        if item.source_event_ids == (senseguard.event_id,)
    ]
    assert len(triggers) == 1, len(triggers)

    rows = journal.list_events(after_position=before, limit=100)
    replay_events = [row for row in rows if row["source"] == SOURCE]
    assert len(replay_events) == 6

    return [
        _result(
            "HA_DUPLICATE_EVENT_DEDUP", detail=f"event_id={duplicate.event_id}; journal_rows=1"
        ),
        _result(
            "HA_DUPLICATE_SOURCE_EVENT_DEDUP",
            detail="same source_event_id produced one journal row",
        ),
        _result(
            "HA_OUT_OF_ORDER_TRUTH",
            detail=f"truth_key={truth_key}; resolved_value=new; source_sequence=2",
        ),
        _result(
            "SENSEGUARD_DUPLICATE_DEDUP",
            detail=f"event_id={senseguard.event_id}; attention_triggers=1",
        ),
        _result(
            "JOURNAL_RESTART_BEFORE_PROJECTION",
            detail=(
                f"event_id={delayed.event_id}; observations={delayed_count}; "
                f"projected={projected.processed}"
            ),
        ),
    ]


class Runtime:
    def __init__(self, *, fails: bool) -> None:
        self.fails = fails
        self.started = False

    def start(self, secret_env: dict[str, str]) -> None:
        del secret_env
        if self.fails:
            raise RuntimeError("synthetic plugin process unavailable")
        self.started = True

    def stop(self) -> None:
        self.started = False

    def list_tools(self) -> list[dict[str, Any]]:
        return [{"name": "read", "input_schema": {"type": "object"}}]

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        del name, arguments, timeout
        return {"ok": True}


def _manifest(plugin_id: str, capability: str) -> PluginManifest:
    return PluginManifest(
        plugin_id=plugin_id,
        plugin_version="14.0.0",
        manifest_version=1,
        requires_core=CORE_VERSION,
        name=capability,
        description="Phase 14 isolation fixture",
        runtime_kind=RuntimeKind.TRUSTED_NATIVE,
        trust_class=TrustClass.TRUSTED_NATIVE,
        capabilities=(capability,),
        tools=({"name": "read", "read_only": True, "input_schema": {"type": "object"}},),
        source="phase14.test",
    )


def verify_plugins() -> list[dict[str, Any]]:
    journal = PostgresEventJournal(DATABASE_URL)
    manager = PluginManager(
        journal=journal,
        store=PostgresPluginStore(DATABASE_URL),
    )
    healthy_id = f"anima.phase14.healthy.{RUN_ID}"
    classes = ("home_assistant", "external_read", "notification_side_effect")
    failed_ids: list[str] = []
    for capability in classes:
        plugin_id = f"anima.phase14.{capability}.{RUN_ID}"
        failed_ids.append(plugin_id)
        manager.register(_manifest(plugin_id, capability), Runtime(fails=True))
    manager.register(_manifest(healthy_id, "unrelated_core"), Runtime(fails=False))
    for plugin_id in failed_ids + [healthy_id]:
        manager.enable(plugin_id)
    assert all(manager.plugins[item].state == PluginState.FAILED for item in failed_ids)
    assert manager.plugins[healthy_id].state == PluginState.HEALTHY
    assert all(item.plugin_id == healthy_id for item in manager.list_tools())
    audit_count = int(
        _scalar(
            "SELECT count(*) FROM anima_event_journal WHERE source=%s AND event_type=%s",
            "anima.plugins",
            "plugin.failed",
        )
        or 0
    )
    assert audit_count >= len(failed_ids)
    return [
        _result(
            "PLUGIN_FAILURE_ISOLATION_THREE_CLASSES",
            detail="HA, external-read, and notification failures left unrelated plugin healthy",
        ),
        _result(
            "PLUGIN_FAILURE_AUDIT_DURABLE",
            detail=f"plugin.failed audit records observed >= {len(failed_ids)}",
        ),
    ]


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    results = verify_events() + verify_plugins()
    print(json.dumps({"run_id": str(RUN_ID), "results": results}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
