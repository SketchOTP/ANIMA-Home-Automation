"""Prove real HA dispatch ambiguity is terminal and never retried.

The isolated Home Assistant service call is real. A test-only connection seam
deliberately hides the post-dispatch state from verification, producing a
governed verification failure. Replaying the same idempotent request must not
call Home Assistant a second time.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_phase6_home_assistant import (  # noqa: E402
    INSTANCE_ID,
    DockerHomeAssistant,
    commission_phase6_graph,
    onboard,
)

from anima_ha.action import (  # noqa: E402
    ActionExecutionCoordinator,
    ActionRequest,
    ActionStatus,
    PostgresActionStore,
    PostgresResourceLocker,
    TruthSnapshot,
    VerificationOutcome,
    VerificationResult,
)
from anima_ha.db.migrate import migrate  # noqa: E402
from anima_ha.fixtures import sample_household_document  # noqa: E402
from anima_ha.graph import PostgresHouseholdGraph  # noqa: E402
from anima_ha.home_assistant import (  # noqa: E402
    HAInstanceConfig,
    HassClientConnection,
    HomeAssistantAdapter,
    HomeAssistantPlugin,
    PostgresHAStore,
)
from anima_ha.journal import PostgresRealityStore  # noqa: E402
from anima_ha.plugins import (  # noqa: E402
    NativeRuntime,
    PluginManager,
    PostgresPluginStore,
    SecretBroker,
)
from anima_ha.policy import (  # noqa: E402
    Assurance,
    IdentityContext,
    OpaPolicyClient,
    PolicyContext,
    PolicyService,
    PostgresPolicyStore,
    RequestOrigin,
)

DATABASE_URL = os.environ.get("ANIMA_DATABASE_URL", "")
OPA_URL = os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181")


class StaleVerificationConnection:
    """Delegate to real HA while hiding post-dispatch state reads."""

    def __init__(self, real: HassClientConnection) -> None:
        self.real = real
        self.hide_state = False
        self.service_calls = 0

    @property
    def version(self) -> str | None:
        return self.real.version

    @property
    def connected(self) -> bool:
        return self.real.connected

    def start(self) -> Any:
        return self.real.start()

    def activate(self) -> list[dict[str, Any]]:
        return self.real.activate()

    def stop(self) -> None:
        self.real.stop()

    def snapshot(self) -> Any:
        return self.real.snapshot()

    def call_service(self, domain: str, service: str, target: dict[str, Any]) -> Any:
        self.service_calls += 1
        result = self.real.call_service(domain, service, target)
        self.hide_state = True
        return result

    def call_service_data(self, domain: str, service: str, data: dict[str, Any]) -> Any:
        return self.real.call_service_data(domain, service, data)

    def get_state(self, entity_id: str) -> dict[str, Any] | None:
        state = self.real.get_state(entity_id)
        if self.hide_state and state is not None:
            return {**state, "state": "off"}
        return state

    def ping(self) -> None:
        self.real.ping()


class CountingGateway:
    def __init__(self, manager: PluginManager) -> None:
        self.manager = manager
        self.calls = 0

    def invoke(self, tool_id: str, arguments: dict[str, Any], **kwargs: Any) -> Any:
        self.calls += 1
        return self.manager.invoke(tool_id, arguments, **kwargs)


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    fixture = DockerHomeAssistant()
    manager: PluginManager | None = None
    try:
        fixture.start_new()
        token = onboard(fixture.base_url)
        websocket_url = fixture.base_url.replace("http://", "ws://") + "/api/websocket"
        config = HAInstanceConfig(
            INSTANCE_ID,
            websocket_url,
            "ANIMA_HA_TOKEN",
            ssl=False,
            verification_timeout=1.0,
            reconnect_backoff_seconds=0.1,
        )
        migrate(DATABASE_URL, 5)
        reality = PostgresRealityStore(DATABASE_URL)
        graph = PostgresHouseholdGraph(DATABASE_URL)
        ha_store = PostgresHAStore(DATABASE_URL)
        policy = PolicyService(
            OpaPolicyClient(OPA_URL), audit_store=PostgresPolicyStore(DATABASE_URL)
        )
        probe = HassClientConnection(
            config,
            token,
            event_callback=lambda event: None,
            disconnect_callback=lambda error: None,
        )
        discovery = probe.start()
        probe.activate()
        probe.stop()
        resource_id, capability_id, _, _, _ = commission_phase6_graph(
            graph, discovery, config.provider_scope
        )
        adapter = HomeAssistantAdapter(config, reality, graph, ha_store)
        connections: list[StaleVerificationConnection] = []

        def connection_factory(current_token: str) -> StaleVerificationConnection:
            real = HassClientConnection(
                config,
                current_token,
                event_callback=adapter.receive_provider_event,
                disconnect_callback=adapter.disconnected,
            )
            wrapped = StaleVerificationConnection(real)
            connections.append(wrapped)
            return wrapped

        plugin = HomeAssistantPlugin(adapter, connection_factory)
        manager = PluginManager(
            journal=reality.journal,
            store=PostgresPluginStore(DATABASE_URL),
            secret_broker=SecretBroker({"ANIMA_HA_TOKEN": token}),
        )
        from anima_ha.home_assistant import home_assistant_manifest

        manifest = home_assistant_manifest(config)
        manager.register(
            manifest,
            NativeRuntime(plugin),
            configuration={"instance_id": str(INSTANCE_ID), "websocket_url": websocket_url},
        )
        if not manager.enable(manifest.plugin_id).enabled:
            raise AssertionError("isolated HA plugin did not enable")
        set_power = next(item for item in manager.list_tools() if item.name == "set_power")

        document = sample_household_document()
        household_id = document.nodes[0].canonical_id
        principal_id = next(node.canonical_id for node in document.nodes if node.name == "Alex")
        identity = IdentityContext(household_id, principal_id, Assurance.AUTHENTICATED)

        def refresh(resources: tuple[UUID, ...]) -> TruthSnapshot:
            state = adapter.read_state(resources[0], capability_id)
            return TruthSnapshot(
                {
                    str(state["truth_key"]): {
                        "state": "KNOWN",
                        "value": state["state"],
                        "version": str(state["observed_at"]),
                    }
                }
            )

        def verify(
            request: ActionRequest, invocation: Any, snapshot: TruthSnapshot
        ) -> VerificationResult:
            expected = "on" if request.arguments["desired_on"] else "off"
            observed = next(iter(snapshot.values.values()))["value"]
            return VerificationResult(
                VerificationOutcome.VERIFIED
                if observed == expected
                else VerificationOutcome.FAILED,
                observed=dict(next(iter(snapshot.values.values()))),
                detail=f"expected={expected}; observed={observed}",
            )

        action = ActionRequest.create(
            action_id=uuid4(),
            action_intent_id=uuid4(),
            idempotency_key=f"phase14-ha-ambiguous-{uuid4()}",
            household_id=household_id,
            tool=set_power,
            arguments={
                "resource_id": str(resource_id),
                "capability_id": str(capability_id),
                "desired_on": True,
            },
            identity=identity,
            policy_service=policy,
            policy_context=PolicyContext(principal_role="owner"),
            refresher=refresh,
            verifier=verify,
            origin=RequestOrigin.DIRECT_USER,
        )
        gateway = CountingGateway(manager)
        coordinator = ActionExecutionCoordinator(
            gateway, PostgresActionStore(DATABASE_URL), PostgresResourceLocker(DATABASE_URL)
        )
        settled = adapter.set_power(resource_id, False, capability_id)
        if settled.observed_state != "off":
            raise AssertionError(f"could not establish off state: {settled}")
        for connection in connections:
            connection.service_calls = 0
        first = coordinator.execute(action)
        if first.record.status != ActionStatus.VERIFICATION_FAILED:
            raise AssertionError(
                f"expected verification failure, got {first.record.status}: {first.record.detail}"
            )
        service_calls = sum(connection.service_calls for connection in connections)
        if service_calls != 1 or gateway.calls != 1:
            raise AssertionError(
                f"expected one real dispatch, service={service_calls}, gateway={gateway.calls}"
            )
        for connection in connections:
            connection.hide_state = False
        actual = adapter.read_state(resource_id, capability_id)
        if actual["state"] != "on":
            raise AssertionError(f"real HA state did not change after service dispatch: {actual}")
        second = coordinator.execute(action)
        if not second.duplicate or second.record.status != ActionStatus.VERIFICATION_FAILED:
            raise AssertionError("replay did not preserve verification failure")
        service_calls = sum(connection.service_calls for connection in connections)
        if service_calls != 1 or gateway.calls != 1:
            raise AssertionError("verification failure was redispatched")
        print(
            json.dumps(
                {
                    "scenario_id": "POSSIBLE_DISPATCH_VERIFICATION_FAILED_NO_RETRY",
                    "status": "PASS",
                    "evidence_level": "ISOLATED_HA_POSTGRES_OPA",
                    "first_status": first.record.status.value,
                    "second_status": second.record.status.value,
                    "real_ha_state_after_fault": actual["state"],
                    "gateway_dispatches": gateway.calls,
                    "ha_service_calls": service_calls,
                    "phase15": False,
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        if manager is not None:
            for registered in list(manager.list_plugins(enabled_only=True)):
                try:
                    manager.disable(registered.manifest.plugin_id)
                except Exception:
                    pass
        fixture.close()


if __name__ == "__main__":
    raise SystemExit(main())
