from __future__ import annotations

import json
import os
import stat
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from anima_ha.intelligence import (
    IntelligenceLifecycle,
    IntelligenceOrigin,
    IntelligenceRequest,
    IntelligenceRequestFactory,
    IntelligenceResult,
    IntelligenceResultStatus,
)
from anima_ha.plugins import (
    ContentPersistence,
    ExecutionBoundary,
    ExternalContentTrust,
    Idempotency,
    ToolDescriptor,
)
from anima_ha.sentry_boundary import (
    CoreSentryBoundary,
    SentryBoundaryError,
    SentryIdentityEvidenceEnvelope,
)
from anima_ha.sentry_service import (
    CoreSentryHTTPService,
    SentryBindingCodec,
    SentryServicePrincipal,
    ServiceAuthError,
    read_credential_file,
)

HOUSEHOLD = UUID("00000000-0000-0000-0000-000000000012")
WORKER = "sentry-shadow-1"


class MemoryStore:
    def __init__(self, request: IntelligenceRequest) -> None:
        self.request = request

    def get(self, request_id: UUID) -> IntelligenceRequest | None:
        return self.request if request_id == self.request.request_id else None

    def transition(
        self,
        request_id: UUID,
        worker_id: str,
        generation: int,
        lifecycle: IntelligenceLifecycle,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        del metadata
        if (
            request_id != self.request.request_id
            or worker_id != self.request.claim_owner
            or generation != self.request.fencing_generation
            or self.request.lease_expires_at is None
            or self.request.lease_expires_at <= datetime.now(UTC)
        ):
            return False
        self.request = replace(
            self.request,
            lifecycle=lifecycle,
            provider_invocation_started=(
                self.request.provider_invocation_started
                or lifecycle == IntelligenceLifecycle.PROVIDER_RUNNING
            ),
        )
        return True


class Manager:
    def __init__(self, tools: list[ToolDescriptor]) -> None:
        self.tools = tools

    def list_tools(self) -> list[ToolDescriptor]:
        return self.tools


def tool(tool_id: str = "anima.test.read") -> ToolDescriptor:
    return ToolDescriptor(
        tool_id=tool_id,
        plugin_id="anima.test",
        capability_id="test.read",
        name="read",
        description="test",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema=None,
        risk_class="READ_ONLY",
        semantic_action="read",
        read_only=True,
        idempotency=Idempotency.IDEMPOTENT,
        timeout=2,
        verification_requirement="NONE",
        external_content_trust=ExternalContentTrust.LOCAL_TRUSTED,
        availability=True,
        version="1",
        provenance="test",
        execution_boundary=ExecutionBoundary.READ_ONLY,
        content_persistence=ContentPersistence.FULL_DURABLE,
    )


def request_for(*, catalogue: tuple[dict[str, object], ...]) -> IntelligenceRequest:
    return IntelligenceRequest(
        request_id=uuid4(),
        household_id=HOUSEHOLD,
        origin=IntelligenceOrigin.DIRECT_SENTRY_INTERACTION,
        context_packet_id=uuid4(),
        context_digest="context",
        catalogue_digest="catalogue",
        provider_id="sentry",
        provider_version="1",
        idempotency_key="request:1",
        lifecycle=IntelligenceLifecycle.PROVIDER_RUNNING,
        claim_owner=WORKER,
        fencing_generation=1,
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        catalogue=catalogue,
    )


def test_sentry_mcp_configuration_contains_only_client_boundary_inputs() -> None:
    config = json.loads(
        Path("integrations/sentry/anima-household/.mcp.json").read_text(encoding="utf-8")
    )
    env = config["mcpServers"]["anima_household"]["env_vars"]
    assert set(env) == {
        "PATH",
        "ANIMA_SENTRY_ENDPOINT",
        "ANIMA_SENTRY_CLIENT_TOKEN_FILE",
        "ANIMA_SENTRY_WORKER_ID",
    }
    assert not any("DATABASE" in value or "HA_" in value or "OPA" in value for value in env)


def test_private_service_credential_rejects_permissive_and_symlink_files(tmp_path: Path) -> None:
    token = "x" * 48
    path = tmp_path / "token"
    path.write_text(token, encoding="utf-8")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    assert read_credential_file(str(path)) == token

    os.chmod(path, 0o644)
    with pytest.raises(ServiceAuthError):
        read_credential_file(str(path))

    link = tmp_path / "token-link"
    link.symlink_to(path)
    with pytest.raises(ServiceAuthError):
        read_credential_file(str(link))


def test_rotating_service_token_revokes_old_authentication() -> None:
    current = {"value": "a" * 48}
    boundary = SimpleNamespace()
    service = CoreSentryHTTPService(cast(Any, boundary), lambda: current["value"])
    service.authenticate({"Authorization": f"Bearer {current['value']}"})
    current["value"] = "b" * 48
    with pytest.raises(ServiceAuthError):
        service.authenticate({"Authorization": "Bearer " + "a" * 48})
    service.authenticate({"Authorization": "Bearer " + "b" * 48})


def test_binding_is_server_issued_and_bound_to_request_identity() -> None:
    request = request_for(catalogue=())
    codec = SentryBindingCodec("s" * 48)
    binding = codec.issue(request, sentry_request_id="sentry-q-1", source_surface="gtk")
    payload = codec.verify(binding, request)
    assert payload["request_id"] == str(request.request_id)
    assert payload["household_id"] == str(HOUSEHOLD)
    assert payload["source_surface"] == "gtk"
    with pytest.raises(ServiceAuthError):
        codec.verify(binding, replace(request, household_id=uuid4()))


def test_provider_start_is_fenced_before_model_execution() -> None:
    request = replace(
        request_for(catalogue=()),
        lifecycle=IntelligenceLifecycle.DELIVERED_TO_PROVIDER,
    )
    store = MemoryStore(request)
    boundary = CoreSentryBoundary(cast(Any, Manager([])), object(), cast(Any, store))

    assert boundary.start_provider(request, WORKER) is True
    current = store.get(request.request_id)
    assert current is not None
    assert current.lifecycle == IntelligenceLifecycle.PROVIDER_RUNNING
    assert current.provider_invocation_started is True

    stale = replace(request, claim_owner="other-worker")
    assert boundary.start_provider(stale, WORKER) is False


def test_direct_request_factory_is_independent_of_attention() -> None:
    request = IntelligenceRequestFactory.for_direct_sentry_interaction(
        sentry_request_id="voice-123",
        household_id=HOUSEHOLD,
        source_surface="gtk",
        user_text="What is the basement state?",
        tools=[tool()],
    )
    assert request.origin == IntelligenceOrigin.DIRECT_SENTRY_INTERACTION
    assert request.trigger_id is None
    assert request.request_metadata["direct_context"]["user_text"] == (
        "What is the basement state?"
    )
    assert request.catalogue[0]["tool_id"] == "anima.test.read"


def test_service_principal_is_server_bound_to_household_and_provider() -> None:
    token = "t" * 48
    principal = SentryServicePrincipal.from_secret(
        client_id="sentry-household-1",
        household_id=HOUSEHOLD,
        provider_id="sentry",
        token=token,
    )
    assert principal.authenticates(token)
    assert not principal.authenticates("x" * 48)
    assert principal.provider_id == "sentry"
    assert principal.household_id == HOUSEHOLD


def test_identity_recording_persists_only_non_escalating_evidence() -> None:
    request = request_for(catalogue=())
    recorded: list[Any] = []
    policy = SimpleNamespace(record_evidence=recorded.append)
    boundary = CoreSentryBoundary(
        cast(Any, Manager([])), policy, cast(Any, MemoryStore(request))
    )
    context = boundary.record_sentry_identity(
        request,
        SentryIdentityEvidenceEnvelope(
            endpoint_id="office",
            profile_state="recognized",
            confidence=100,
            observed_at=datetime.now(UTC),
            local_proximity=True,
            spoken_identity_claim="Sketch",
        ),
        profile_principal_id=uuid4(),
    )
    assert len(recorded) == 1
    assert context.assurance.value == "RECOGNIZED"


def test_request_catalogue_is_frozen_and_new_global_tools_are_not_visible() -> None:
    original = tool()
    digest = CoreSentryBoundary._schema_digest(original.input_schema)
    request = request_for(
        catalogue=(
            {
                "tool_id": original.tool_id,
                "plugin_id": original.plugin_id,
                "version": original.version,
                "schema_digest": digest,
                "availability": True,
            },
        )
    )
    manager = Manager([original, tool("anima.test.new")])
    boundary = CoreSentryBoundary(cast(Any, manager), object(), cast(Any, MemoryStore(request)))
    visible = boundary.catalogue(request)
    assert [item["tool_id"] for item in visible] == [original.tool_id]
    assert boundary._request_tool(request, original.tool_id) is original

    manager.tools = []
    with pytest.raises(SentryBoundaryError, match="TOOL_UNAVAILABLE"):
        boundary._request_tool(request, original.tool_id)


def test_stale_fencing_generation_cannot_invoke_or_submit() -> None:
    original = tool()
    digest = CoreSentryBoundary._schema_digest(original.input_schema)
    request = request_for(
        catalogue=(
            {
                "tool_id": original.tool_id,
                "plugin_id": original.plugin_id,
                "version": original.version,
                "schema_digest": digest,
                "availability": True,
            },
        )
    )
    store = MemoryStore(request)
    boundary = CoreSentryBoundary(cast(Any, Manager([original])), object(), cast(Any, store))
    store.request = replace(request, fencing_generation=2, claim_owner="new-owner")
    with pytest.raises(SentryBoundaryError, match="INTELLIGENCE_CLAIM_LOST"):
        boundary.invoke_tool(request, original.tool_id, {})
    with pytest.raises(SentryBoundaryError, match="INTELLIGENCE_CLAIM_LOST"):
        boundary.submit_result(
            request,
            WORKER,
            IntelligenceResult(request.request_id, IntelligenceResultStatus.RESPONSE, "done"),
        )


def test_sentry_identity_evidence_never_escalates_to_authentication() -> None:
    envelope = SentryIdentityEvidenceEnvelope(
        endpoint_id="office-endpoint",
        profile_state="recognized",
        confidence=99,
        observed_at=datetime.now(UTC),
        local_proximity=True,
        spoken_identity_claim="Sketch",
    )
    evidence = envelope.to_anima_evidence(HOUSEHOLD, uuid4())
    assert evidence.assurance.value == "RECOGNIZED"
    assert evidence.strength <= 50
    assert evidence.evidence_type.value == "LOCAL_PROXIMITY"


def test_expired_or_ambiguous_sentry_observation_cannot_name_a_principal() -> None:
    evidence = SentryIdentityEvidenceEnvelope(
        endpoint_id="office-endpoint",
        profile_state="expired",
        confidence=99,
        observed_at=datetime.now(UTC),
        state="expired",
    ).to_anima_evidence(HOUSEHOLD, uuid4())
    assert evidence.claimed_principal_id is None
    assert evidence.metadata["usable_for_principal_candidate"] is False
