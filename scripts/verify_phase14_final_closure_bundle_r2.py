"""Run the final four Phase 14 residuals as one bounded qualification bundle.

The bundle deliberately exercises the real PostgreSQL stores, the running OPA
container, the running UI/Core container, and an isolated Home Assistant
container.  It is an evidence runner, not a new runtime or fault-injection
framework.  The SENTRY/ANIMA bridge remains represented by its durable stores;
the separate SENTRY process matrix supplies the provider lifecycle evidence.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_phase6_home_assistant import (
    INSTANCE_ID,
    DockerHomeAssistant,
    commission_phase6_graph,
    onboard,
)
from scripts.verify_phase12_h5u_confirmation import tool

from anima_ha.action import (
    ActionExecutionCoordinator,
    ActionRequest,
    ActionStatus,
    PostgresActionStore,
    PostgresPendingApprovalStore,
    PostgresResourceLocker,
    TruthSnapshot,
    VerificationOutcome,
    VerificationResult,
)
from anima_ha.db.migrate import migrate
from anima_ha.fixtures import sample_household_document
from anima_ha.graph import PostgresHouseholdGraph
from anima_ha.home_assistant import (
    HAInstanceConfig,
    HassClientConnection,
    HomeAssistantAdapter,
    HomeAssistantPlugin,
    PostgresHAStore,
    home_assistant_manifest,
)
from anima_ha.journal import PostgresRealityStore
from anima_ha.plugins import (
    ExternalContentTrust,
    InvocationOutcome,
    InvocationResult,
    NativeRuntime,
    PluginManager,
    PostgresPluginStore,
    SecretBroker,
)
from anima_ha.policy import (
    Assurance,
    IdentityContext,
    OpaPolicyClient,
    PolicyContext,
    PolicyService,
    PostgresPolicyStore,
)

DATABASE_URL = os.environ.get("ANIMA_DATABASE_URL", "")
OPA_URL = os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181")
UI_PORT = os.environ.get("ANIMA_UI_PORT", "18090")


def compose(*args: str) -> str:
    project = os.environ.get("ANIMA_COMPOSE_PROJECT", "")
    command = ["docker", "compose"]
    if project:
        command.extend(("-p", project))
    return subprocess.run(
        [*command, *args], check=True, text=True, capture_output=True
    ).stdout.strip()


def metadata(service: str) -> dict[str, str]:
    container_id = compose("ps", "-q", service)
    if not container_id:
        raise AssertionError(f"missing running Compose service {service}")
    values = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            "{{.Id}}|{{.State.Pid}}|{{.State.StartedAt}}|{{.State.Status}}",
            container_id,
        ],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip().split("|", 3)
    if len(values) != 4:
        raise AssertionError(f"invalid metadata for {service}")
    return {"container_id": values[0], "pid": values[1], "started_at": values[2], "status": values[3]}


def wait_http(url: str) -> None:
    import urllib.request

    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if 200 <= response.status < 400:
                    return
        except Exception:
            time.sleep(1)
    raise TimeoutError(f"service did not recover: {url}")


def fixture_metadata(fixture: DockerHomeAssistant) -> dict[str, str]:
    values = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            "{{.Id}}|{{.State.Pid}}|{{.State.StartedAt}}|{{.State.Status}}",
            fixture.name,
        ],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip().split("|", 3)
    if len(values) != 4:
        raise AssertionError("invalid isolated Home Assistant metadata")
    return {"container_id": values[0], "pid": values[1], "started_at": values[2], "status": values[3]}


class CountingGateway:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, *args: Any, **kwargs: Any) -> InvocationResult:
        del args, kwargs
        self.calls += 1
        return InvocationResult(
            InvocationOutcome.SUCCESS,
            "anima.phase14.final",
            "anima.phase14",
            "1.0.0",
            0.01,
            result={"accepted": True},
            external_content_trust=ExternalContentTrust.PLUGIN_TRUSTED,
        )


class ConfirmationOnly:
    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        del document
        return {
            "decision": "REQUIRE_CONFIRMATION",
            "reason_code": "CONFIRMATION_REQUIRED",
            "required_assurance": "AUTHENTICATED",
            "confirmation_required": True,
            "policy_version": "phase14-final-confirmation",
        }


class Allow:
    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        del document
        return {
            "decision": "ALLOW",
            "reason_code": "CURRENT_POLICY_ALLOWED",
            "required_assurance": "AUTHENTICATED",
            "confirmation_required": False,
            "policy_version": "phase14-final-allow",
        }


def action_request(policy: PolicyService, principal: UUID, label: str) -> ActionRequest:
    return ActionRequest.create(
        action_id=uuid4(),
        action_intent_id=uuid4(),
        idempotency_key=f"phase14-final-{label}-{uuid4()}",
        household_id=UUID("ecbd0d84-6f5f-40f8-928f-1d5dfe758dd7"),
        tool=tool(),
        arguments={"resource_id": str(uuid4()), "desired_on": True},
        identity=IdentityContext(
            UUID("ecbd0d84-6f5f-40f8-928f-1d5dfe758dd7"), principal, Assurance.AUTHENTICATED
        ),
        policy_service=policy,
        policy_context=PolicyContext(principal_role="resident"),
        refresher=lambda resources: TruthSnapshot(
            {"power": {"state": "KNOWN", "value": "off", "version": "1"}}
        ),
    )


def rejection(results: list[dict[str, Any]]) -> None:
    pending = PostgresPendingApprovalStore(DATABASE_URL)
    gateway = CountingGateway()
    coordinator = ActionExecutionCoordinator(
        gateway,
        PostgresActionStore(DATABASE_URL),
        PostgresResourceLocker(DATABASE_URL),
        pending_approvals=pending,
    )
    principal = uuid4()
    request = action_request(PolicyService(ConfirmationOnly(), audit_store=PostgresPolicyStore(DATABASE_URL)), principal, "reject")
    waiting = coordinator.execute(request)
    assert waiting.record.status == ActionStatus.REQUIRE_CONFIRMATION
    assert waiting.record.result and waiting.record.result.get("approval_id")
    approval_id = UUID(str(waiting.record.result["approval_id"]))
    execution = coordinator.approve_pending(
        approval_id,
        household_id=request.household_id,
        principal_id=principal,
        decision="REJECT",
        tool=request.tool,
        policy_service=PolicyService(Allow(), audit_store=PostgresPolicyStore(DATABASE_URL)),
    )
    stored = pending.get(approval_id)
    assert execution is not None and stored is not None
    assert stored.status.value == "REJECTED"
    assert execution.record.status == ActionStatus.POLICY_DENIED
    assert gateway.calls == 0
    results.append(
        {
            "scenario_id": "REJECTION_NOT_POLICY_DENIAL",
            "status": "PASSED",
            "evidence_level": "POSTGRES_ACTION_UI_PROJECTION",
            "approval_status": stored.status.value,
            "action_status": execution.record.status.value,
            "provider_dispatches": gateway.calls,
            "semantic_user_result": "REJECTED",
            "durable_approval_id": str(approval_id),
        }
    )


def core_restart(results: list[dict[str, Any]]) -> None:
    before = metadata("ui")
    pending = PostgresPendingApprovalStore(DATABASE_URL)
    gateway = CountingGateway()
    coordinator = ActionExecutionCoordinator(
        gateway,
        PostgresActionStore(DATABASE_URL),
        PostgresResourceLocker(DATABASE_URL),
        pending_approvals=pending,
    )
    principal = uuid4()
    refresh_states = iter(
        [
            TruthSnapshot({"power": {"state": "KNOWN", "value": "off", "version": "1"}}),
            TruthSnapshot({"power": {"state": "KNOWN", "value": "off", "version": "2"}}),
            TruthSnapshot({"power": {"state": "KNOWN", "value": "on", "version": "3"}}),
        ]
    )
    request = action_request(
        PolicyService(ConfirmationOnly(), audit_store=PostgresPolicyStore(DATABASE_URL)),
        principal,
        "core-restart",
    )
    request = replace(request, refresher=lambda resources: next(refresh_states))
    waiting = coordinator.execute(request)
    assert waiting.record.status == ActionStatus.REQUIRE_CONFIRMATION
    approval_id = UUID(str(waiting.record.result["approval_id"]))  # type: ignore[index]
    compose("restart", "ui")
    wait_http(f"http://127.0.0.1:{UI_PORT}/healthz")
    after = metadata("ui")
    recovered = pending.get(approval_id)
    assert recovered is not None and recovered.status.value == "PENDING"
    resumed = coordinator.approve_pending(
        approval_id,
        household_id=request.household_id,
        principal_id=principal,
        decision="APPROVE",
        tool=request.tool,
        policy_service=PolicyService(Allow()),
        refresher=lambda resources: next(refresh_states),
    )
    assert resumed is not None and resumed.record.status == ActionStatus.SUCCEEDED, (
        f"restart approval terminal status={resumed.record.status.value if resumed else None} "
        f"detail={resumed.record.detail if resumed else None} "
        f"result={resumed.record.result if resumed else None}"
    )
    assert gateway.calls == 1
    assert before["started_at"] != after["started_at"] or before["pid"] != after["pid"]
    results.append(
        {
            "scenario_id": "CORE_RESTART_INFLIGHT",
            "status": "PASSED",
            "evidence_level": "POSTGRES_CORE_PROCESS",
            "state_before_restart": "REQUIRE_CONFIRMATION",
            "state_after_restart": recovered.status.value,
            "terminal_state": resumed.record.status.value,
            "provider_dispatches": gateway.calls,
            "container_identity_preserved": before["container_id"] == after["container_id"],
            "before": before,
            "after": after,
            "approval_id": str(approval_id),
        }
    )


def opa_restart(results: list[dict[str, Any]]) -> None:
    before = metadata("opa")
    compose("restart", "opa")
    wait_http(f"{OPA_URL}/health")
    after = metadata("opa")
    assert before["started_at"] != after["started_at"] or before["pid"] != after["pid"]
    policy = PolicyService(OpaPolicyClient(OPA_URL), audit_store=PostgresPolicyStore(DATABASE_URL))
    gateway = CountingGateway()
    coordinator = ActionExecutionCoordinator(
        gateway, PostgresActionStore(DATABASE_URL), PostgresResourceLocker(DATABASE_URL)
    )
    request = action_request(policy, uuid4(), "opa-restart")
    result = coordinator.execute(request)
    assert result.record.status == ActionStatus.SUCCEEDED
    assert gateway.calls == 1
    results.append(
        {
            "scenario_id": "OPA_RESTART_INFLIGHT",
            "status": "PASSED",
            "evidence_level": "POSTGRES_OPA_CORE_PROCESS",
            "terminal_state": result.record.status.value,
            "provider_dispatches": gateway.calls,
            "container_identity_preserved": before["container_id"] == after["container_id"],
            "before": before,
            "after": after,
            "policy_source": "running_unmodified_opa",
        }
    )


class RestartAfterDispatchConnection:
    def __init__(self, delegate: HassClientConnection, fixture: DockerHomeAssistant) -> None:
        self.delegate = delegate
        self.fixture = fixture
        self.restart_metadata: tuple[dict[str, str], dict[str, str]] | None = None
        self.service_calls = 0

    @property
    def version(self) -> str | None:
        return self.delegate.version

    @property
    def connected(self) -> bool:
        return self.delegate.connected

    def start(self) -> Any:
        return self.delegate.start()

    def activate(self) -> list[dict[str, Any]]:
        return self.delegate.activate()

    def stop(self) -> None:
        self.delegate.stop()

    def snapshot(self) -> Any:
        return self.delegate.snapshot()

    def call_service(self, domain: str, service: str, target: dict[str, Any]) -> Any:
        self.service_calls += 1
        result = self.delegate.call_service(domain, service, target)
        if self.restart_metadata is None:
            before = fixture_metadata(self.fixture)
            self.fixture.stop()
            self.fixture.restart()
            self.restart_metadata = (before, fixture_metadata(self.fixture))
        return result

    def call_service_data(self, domain: str, service: str, data: dict[str, Any]) -> Any:
        return self.delegate.call_service_data(domain, service, data)

    def get_state(self, entity_id: str) -> dict[str, Any] | None:
        return self.delegate.get_state(entity_id)

    def ping(self) -> None:
        self.delegate.ping()


def ha_restart(results: list[dict[str, Any]]) -> None:
    fixture = DockerHomeAssistant()
    manager: PluginManager | None = None
    try:
        fixture.start_new()
        token = onboard(fixture.base_url)
        websocket_url = fixture.base_url.replace("http://", "ws://") + "/api/websocket"
        config = HAInstanceConfig(
            INSTANCE_ID, websocket_url, "ANIMA_HA_TOKEN", ssl=False, verification_timeout=1.0
        )
        reality = PostgresRealityStore(DATABASE_URL)
        graph = PostgresHouseholdGraph(DATABASE_URL)
        store = PostgresHAStore(DATABASE_URL)
        probe = HassClientConnection(config, token, event_callback=lambda event: None, disconnect_callback=lambda error: None)
        discovery = probe.start()
        probe.activate()
        probe.stop()
        resource_id, capability_id, _, _, _ = commission_phase6_graph(graph, discovery, config.provider_scope)
        adapter = HomeAssistantAdapter(config, reality, graph, store)
        connections: list[RestartAfterDispatchConnection] = []

        def factory(current_token: str) -> RestartAfterDispatchConnection:
            wrapped = RestartAfterDispatchConnection(
                HassClientConnection(
                    config,
                    current_token,
                    event_callback=adapter.receive_provider_event,
                    disconnect_callback=adapter.disconnected,
                ),
                fixture,
            )
            connections.append(wrapped)
            return wrapped

        plugin = HomeAssistantPlugin(adapter, factory)
        manager = PluginManager(
            journal=reality.journal,
            store=PostgresPluginStore(DATABASE_URL),
            secret_broker=SecretBroker({"ANIMA_HA_TOKEN": token}),
        )
        manifest = home_assistant_manifest(config)
        manager.register(manifest, NativeRuntime(plugin), configuration={"instance_id": str(INSTANCE_ID), "websocket_url": websocket_url})
        assert manager.enable(manifest.plugin_id).enabled
        set_power = next(item for item in manager.list_tools() if item.name == "set_power")
        document = sample_household_document()
        household_id = document.nodes[0].canonical_id
        principal_id = next(node.canonical_id for node in document.nodes if node.name == "Alex")
        identity = IdentityContext(household_id, principal_id, Assurance.AUTHENTICATED)

        def refresh(resources: tuple[UUID, ...]) -> TruthSnapshot:
            state = adapter.read_state(resources[0], capability_id)
            return TruthSnapshot({str(state["truth_key"]): {"state": "KNOWN", "value": state["state"], "version": str(state["observed_at"])}})

        def verify(request: ActionRequest, invocation: Any, snapshot: TruthSnapshot) -> VerificationResult:
            del invocation
            expected = "on" if request.arguments["desired_on"] else "off"
            observed = next(iter(snapshot.values.values()))["value"]
            return VerificationResult(
                VerificationOutcome.VERIFIED if observed == expected else VerificationOutcome.FAILED,
                observed=dict(next(iter(snapshot.values.values()))),
                detail=f"expected={expected}; observed={observed}",
            )

        assert adapter.set_power(resource_id, False, capability_id).observed_state == "off"
        action = ActionRequest.create(
            action_id=uuid4(), action_intent_id=uuid4(), idempotency_key=f"phase14-ha-restart-{uuid4()}",
            household_id=household_id, tool=set_power,
            arguments={"resource_id": str(resource_id), "capability_id": str(capability_id), "desired_on": True},
            identity=identity, policy_service=PolicyService(OpaPolicyClient(OPA_URL), audit_store=PostgresPolicyStore(DATABASE_URL)),
            policy_context=PolicyContext(principal_role="owner"), refresher=refresh, verifier=verify,
        )
        coordinator = ActionExecutionCoordinator(manager, PostgresActionStore(DATABASE_URL), PostgresResourceLocker(DATABASE_URL))
        first = coordinator.execute(action)
        assert connections[0].restart_metadata is not None
        assert first.record.status in {ActionStatus.SUCCEEDED, ActionStatus.UNKNOWN_RESULT, ActionStatus.VERIFICATION_FAILED}
        dispatches = sum(connection.service_calls for connection in connections)
        assert dispatches == 1
        assert adapter.reconnect(lambda: factory(token)) is True
        replay = coordinator.execute(action)
        assert replay.duplicate is True and sum(connection.service_calls for connection in connections) == 1
        results.append(
            {
                "scenario_id": "HA_RESTART_INFLIGHT",
                "status": "PASSED",
                "evidence_level": "ISOLATED_HA_POSTGRES_OPA_PROCESS",
                "terminal_state": first.record.status.value,
                "replay_state": replay.record.status.value,
                "provider_dispatches": dispatches,
                "container_before": connections[0].restart_metadata[0],
                "container_after": connections[0].restart_metadata[1],
                "reconnected_health": adapter.status.health.value,
            }
        )
    finally:
        if manager is not None:
            for registered in list(manager.list_plugins(enabled_only=True)):
                try:
                    manager.disable(registered.manifest.plugin_id)
                except Exception:
                    pass
        fixture.close()


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    migrate(DATABASE_URL, 5)
    results: list[dict[str, Any]] = []
    rejection(results)
    core_restart(results)
    opa_restart(results)
    ha_restart(results)
    assert all(item["status"] == "PASSED" for item in results)
    print(json.dumps({"scenario_id": "PHASE14_FINAL_CLOSURE_BUNDLE", "status": "PASS", "evidence_level": "REAL_STORE_PROCESS", "tested_sha": os.environ.get("GITHUB_SHA", "local"), "results": results, "checked_at": datetime.now(UTC).isoformat(), "native_pi5": "EXTERNAL_RESOURCE_GATE_NATIVE_PI5", "phase15": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
