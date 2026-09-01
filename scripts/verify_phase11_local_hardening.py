"""Target evidence for the Phase 11 local-calendar policy and PostgreSQL store."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import psycopg

from anima_ha.calendar import (
    CALENDAR_MANIFEST,
    CalendarConflict,
    CalendarNativePlugin,
    CalendarNotFound,
    CalendarService,
    CalendarStatus,
    PostgresCalendarStore,
)
from anima_ha.config import RuntimeConfig
from anima_ha.events import EventEnvelope
from anima_ha.plugins import (
    InvocationContext,
    InvocationOutcome,
    NativeRuntime,
    PluginManager,
    SecretBroker,
)
from anima_ha.policy import (
    Assurance,
    IdentityContext,
    OpaPolicyClient,
    PolicyContext,
    PolicyService,
    RequestOrigin,
)

HOUSEHOLD = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PRINCIPAL = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
EPISODE = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _context(key: str, *, principal_id: UUID | None = PRINCIPAL) -> InvocationContext:
    return InvocationContext(
        household_id=HOUSEHOLD,
        principal_id=principal_id,
        episode_id=EPISODE,
        tool_request_id=uuid4(),
        ordinal=1,
        system_idempotency_key=key,
        origin=RequestOrigin.DIRECT_USER,
    )


def _arguments(title: str = "Phase 11 target event") -> dict[str, str]:
    start = datetime.now(UTC).replace(microsecond=0) + timedelta(days=30)
    return {
        "title": title,
        "start_at": start.isoformat(),
        "end_at": (start + timedelta(minutes=30)).isoformat(),
        "timezone": "UTC",
    }


def _action_count(database_url: str) -> int:
    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM anima_actions WHERE household_id=%s", (HOUSEHOLD,))
        return int(cursor.fetchone()[0])


def main() -> int:
    config = RuntimeConfig.from_environment()
    opa_url = os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181")
    store = PostgresCalendarStore(config.database_url, config.database_connect_timeout)
    audit_events: list[EventEnvelope] = []
    service = CalendarService(store, event_sink=audit_events)
    manager = PluginManager(secret_broker=SecretBroker({}))
    manager.register(CALENDAR_MANIFEST, NativeRuntime(CalendarNativePlugin(service)))
    manager.enable(CALENDAR_MANIFEST.plugin_id)
    policy = PolicyService(OpaPolicyClient(opa_url))
    authorized = IdentityContext(HOUSEHOLD, PRINCIPAL, Assurance.AUTHENTICATED)
    resident = PolicyContext(principal_role="resident")
    invocation_key = f"phase11-local-calendar-target:{uuid4()}"
    invocation = _context(invocation_key)
    args = _arguments()
    before_actions = _action_count(config.database_url)

    allowed = manager.invoke(
        "anima.calendar.create_event",
        args,
        household_id=HOUSEHOLD,
        identity=authorized,
        origin=RequestOrigin.DIRECT_USER,
        policy_service=policy,
        policy_context=resident,
        invocation_context=invocation,
    )
    assert allowed.outcome == InvocationOutcome.SUCCESS, allowed
    event_id = UUID(str(allowed.result["event"]["event_id"]))
    assert allowed.policy_decision is not None
    assert allowed.policy_decision.decision.value == "ALLOW"
    print(f"real_opa_calendar_allow=PASS decision={allowed.policy_decision.reason_code}")

    replay = manager.invoke(
        "anima.calendar.create_event",
        args,
        household_id=HOUSEHOLD,
        identity=authorized,
        origin=RequestOrigin.DIRECT_USER,
        policy_service=policy,
        policy_context=resident,
        invocation_context=invocation,
    )
    assert replay.outcome == InvocationOutcome.SUCCESS
    assert UUID(str(replay.result["event"]["event_id"])) == event_id
    with psycopg.connect(config.database_url) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM anima_calendar_events WHERE event_id=%s", (event_id,))
        assert cursor.fetchone()[0] == 1
    print("postgres_calendar_create_replay=PASS one_row=true")

    misuse = _context(invocation_key)
    try:
        service.create(context=misuse, arguments={**args, "title": "different fingerprint"})
    except CalendarConflict:
        print("postgres_calendar_creation_key_conflict=PASS")
    else:
        raise AssertionError("creation-key misuse was not rejected")

    fetched = service.get(household_id=HOUSEHOLD, event_id=event_id)
    assert fetched.status == CalendarStatus.ACTIVE
    listed = service.list_events(
        household_id=HOUSEHOLD,
        start_at=fetched.start_at - timedelta(minutes=1),
        end_at=fetched.end_at + timedelta(minutes=1),
        limit=10,
    )
    assert [item.event_id for item in listed] == [event_id]
    updated = service.update(
        context=_context("phase11-local-calendar-update"),
        event_id=event_id,
        expected_version=1,
        changes={"title": "Phase 11 target event updated"},
    )
    assert updated.version == 2
    try:
        service.update(
            context=_context("phase11-local-calendar-stale"),
            event_id=event_id,
            expected_version=1,
            changes={"title": "must not apply"},
        )
    except CalendarConflict:
        pass
    else:
        raise AssertionError("stale update was not rejected")
    cancelled = service.cancel(
        context=_context("phase11-local-calendar-cancel"), event_id=event_id, expected_version=2
    )
    assert cancelled.status == CalendarStatus.CANCELLED and cancelled.version == 3
    assert (
        service.cancel(
            context=_context("phase11-local-calendar-cancel-replay"),
            event_id=event_id,
            expected_version=1,
        ).version
        == 3
    )
    listed_cancelled = service.list_events(
        household_id=HOUSEHOLD,
        start_at=fetched.start_at - timedelta(minutes=1),
        end_at=fetched.end_at + timedelta(minutes=1),
        limit=10,
        include_cancelled=True,
    )
    assert listed_cancelled[0].status == CalendarStatus.CANCELLED
    assert len(audit_events) == 3
    assert audit_events[1].payload["principal_id"] == str(PRINCIPAL)
    assert audit_events[1].payload["version"] == 2
    print("calendar_audit_trusted_provenance=PASS create_update_cancel=3")
    restarted = PostgresCalendarStore(config.database_url, config.database_connect_timeout)
    assert restarted.get(HOUSEHOLD, event_id).status == CalendarStatus.CANCELLED
    print("postgres_calendar_crud_version_restart=PASS")

    other_household = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    try:
        restarted.get(other_household, event_id)
    except CalendarNotFound:
        pass
    else:
        raise AssertionError("cross-household calendar read was allowed")
    assert _action_count(config.database_url) == before_actions
    print("postgres_calendar_household_isolation_no_phase9_record=PASS")

    denied = manager.invoke(
        "anima.calendar.create_event",
        _arguments("must not persist"),
        household_id=HOUSEHOLD,
        identity=IdentityContext(HOUSEHOLD, None, Assurance.ANONYMOUS),
        origin=RequestOrigin.DIRECT_USER,
        policy_service=policy,
        policy_context=PolicyContext(),
        invocation_context=_context("phase11-local-calendar-denied", principal_id=None),
    )
    assert denied.outcome == InvocationOutcome.POLICY_DENIED, denied
    assert _action_count(config.database_url) == before_actions
    print(f"real_opa_calendar_insufficient_identity=PASS reason={denied.error_class}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
