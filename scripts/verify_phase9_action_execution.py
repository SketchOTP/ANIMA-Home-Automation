"""Real isolated Home Assistant evidence for the Phase 9 action coordinator."""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_phase6_home_assistant import (
    INSTANCE_ID,
    DockerHomeAssistant,
    commission_phase6_graph,
    onboard,
)

from anima_ha.action import (
    ActionExecutionCoordinator,
    ActionRequest,
    ActionStatus,
    PostgresActionStore,
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
from anima_ha.plugins import NativeRuntime, PluginManager, PostgresPluginStore, SecretBroker
from anima_ha.policy import (
    Assurance,
    IdentityContext,
    OpaPolicyClient,
    PolicyContext,
    PolicyService,
    PostgresPolicyStore,
)

DATABASE_URL = os.environ.get(
    "ANIMA_DATABASE_URL", "postgresql://anima:anima_dev_only@localhost:55432/anima"
)
OPA_URL = os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181")


class SlowGateway:
    """Hold the canonical resource lock while a real HA call is in flight."""

    def __init__(self, manager: PluginManager) -> None:
        self.manager = manager
        self.started = threading.Event()
        self.calls = 0

    def invoke(self, tool_id: str, arguments: dict[str, Any], **kwargs: Any) -> Any:
        self.calls += 1
        self.started.set()
        time.sleep(0.5)
        return self.manager.invoke(tool_id, arguments, **kwargs)


def main() -> int:
    fixture = DockerHomeAssistant()
    manager: PluginManager | None = None
    token = ""
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
        plugin_store = PostgresPluginStore(DATABASE_URL)
        policy = PolicyService(
            OpaPolicyClient(OPA_URL), audit_store=PostgresPolicyStore(DATABASE_URL)
        )
        probe = HassClientConnection(
            config, token, event_callback=lambda event: None, disconnect_callback=lambda error: None
        )
        discovery = probe.start()
        probe.activate()
        probe.stop()
        resource_id, capability_id, _, _, _ = commission_phase6_graph(
            graph, discovery, config.provider_scope
        )
        adapter = HomeAssistantAdapter(config, reality, graph, ha_store)

        def connection_factory(current_token: str) -> HassClientConnection:
            return HassClientConnection(
                config,
                current_token,
                event_callback=adapter.receive_provider_event,
                disconnect_callback=adapter.disconnected,
            )

        plugin = HomeAssistantPlugin(adapter, connection_factory)
        manager = PluginManager(
            journal=reality.journal,
            store=plugin_store,
            secret_broker=SecretBroker({"ANIMA_HA_TOKEN": token}),
        )
        manifest = home_assistant_manifest(config)
        manager.register(
            manifest,
            NativeRuntime(plugin),
            configuration={"instance_id": str(INSTANCE_ID), "websocket_url": websocket_url},
        )
        assert manager.enable(manifest.plugin_id).enabled
        tool = next(item for item in manager.list_tools() if item.name == "set_power")
        document = sample_household_document()
        household_id = document.nodes[0].canonical_id
        principal_id = next(node.canonical_id for node in document.nodes if node.name == "Alex")
        second_principal_id = next(
            node.canonical_id for node in document.nodes if node.name == "Sam"
        )
        identity = IdentityContext(household_id, principal_id, Assurance.AUTHENTICATED)
        second_identity = IdentityContext(
            household_id, second_principal_id, Assurance.AUTHENTICATED
        )
        context = PolicyContext(principal_role="owner")

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

        def build_request(
            key: str, desired_on: bool, action_identity: IdentityContext = identity
        ) -> ActionRequest:
            return ActionRequest.create(
                idempotency_key=key,
                household_id=household_id,
                tool=tool,
                arguments={
                    "resource_id": str(resource_id),
                    "capability_id": str(capability_id),
                    "desired_on": desired_on,
                },
                identity=action_identity,
                policy_service=policy,
                policy_context=context,
                refresher=refresh,
                verifier=verify,
            )

        store = PostgresActionStore(DATABASE_URL)
        coordinator = ActionExecutionCoordinator(
            manager, store, PostgresResourceLocker(DATABASE_URL)
        )
        gateway = SlowGateway(manager)
        race_coordinator = ActionExecutionCoordinator(
            gateway, store, PostgresResourceLocker(DATABASE_URL)
        )
        first = build_request(f"phase9-live-{uuid4()}-first", True)
        second = build_request(f"phase9-live-{uuid4()}-second", False, second_identity)
        results: dict[str, Any] = {}

        def run_first() -> None:
            results["first"] = race_coordinator.execute(first)

        thread = threading.Thread(target=run_first)
        thread.start()
        assert gateway.started.wait(timeout=5), "real HA gateway did not begin"
        results["second"] = coordinator.execute(second)
        thread.join(timeout=15)
        assert not thread.is_alive()
        assert results["first"].record.status == ActionStatus.SUCCEEDED
        assert results["second"].record.status == ActionStatus.RESOURCE_BUSY
        assert gateway.calls == 1

        replay = coordinator.execute(first)
        assert replay.duplicate is True
        assert replay.record.status == ActionStatus.SUCCEEDED
        print("PHASE9_REAL_HOME_ASSISTANT_ACTION_COORDINATOR_PASS")
        print(f"ha_version={discovery.version}")
        print("resource_lock=real PostgreSQL session advisory-lock race; busy request not queued")
        print("contradictory_users=Alex on versus Sam off; conflict resolved before connector")
        print("connector=real isolated Home Assistant set_power service + observed state")
        print("verification=post-action adapter refresh matched requested state")
        print("idempotency=real PostgreSQL replay returned durable result without second call")
        return 0
    finally:
        if manager is not None:
            for registered in list(manager.list_plugins(enabled_only=True)):
                try:
                    manager.disable(registered.manifest.plugin_id)
                except Exception:
                    pass
        token = ""
        fixture.close()


if __name__ == "__main__":
    raise SystemExit(main())
