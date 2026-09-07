from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from anima_ha.plugins import (
    ContentPersistence,
    ExecutionBoundary,
    ExternalContentTrust,
    Idempotency,
    ToolDescriptor,
)
from anima_ha.sentry_boundary import CoreSentryBoundary

PRINCIPAL = UUID("00000000-0000-0000-0000-000000000013")


def _tool(*, tool_id: str, read_only: bool) -> ToolDescriptor:
    return ToolDescriptor(
        tool_id=tool_id,
        plugin_id=tool_id.rsplit(".", 1)[0],
        capability_id="test.capability",
        name=tool_id.rsplit(".", 1)[-1],
        description="test",
        input_schema={"type": "object", "additionalProperties": True},
        output_schema=None,
        risk_class="READ_ONLY" if read_only else "SECURITY_SECURE_ACTION",
        semantic_action="test",
        read_only=read_only,
        idempotency=Idempotency.IDEMPOTENT,
        timeout=2,
        verification_requirement="NONE",
        external_content_trust=ExternalContentTrust.LOCAL_TRUSTED,
        availability=True,
        version="1",
        provenance="test",
        execution_boundary=(
            ExecutionBoundary.READ_ONLY
            if read_only
            else ExecutionBoundary.POLICY_GATED_INTERNAL
        ),
        content_persistence=ContentPersistence.FULL_DURABLE,
    )


def test_limited_sentry_access_allows_reads_only_and_own_personal_preferences() -> None:
    read = _tool(tool_id="anima.household-users.list_users", read_only=True)
    personal = _tool(
        tool_id="anima.household-preferences.create_preference", read_only=False
    )
    household = _tool(tool_id="anima.household-users.update_user", read_only=False)

    assert CoreSentryBoundary._limited_tool_allowed(read, {}, PRINCIPAL)
    assert CoreSentryBoundary._limited_tool_allowed(
        personal, {"person_id": str(PRINCIPAL)}, PRINCIPAL
    )
    assert not CoreSentryBoundary._limited_tool_allowed(personal, {}, PRINCIPAL)
    assert not CoreSentryBoundary._limited_tool_allowed(
        personal, {"person_id": str(UUID("00000000-0000-0000-0000-000000000099"))}, PRINCIPAL
    )
    assert not CoreSentryBoundary._limited_tool_allowed(household, {}, PRINCIPAL)


def test_unconfigured_test_boundary_retains_legacy_policy_path() -> None:
    assert CoreSentryBoundary._access_level(
        SimpleNamespace(access_level_resolver=None),
        type("Request", (), {"principal_id": None})(),
    ) == "UNRESTRICTED"
