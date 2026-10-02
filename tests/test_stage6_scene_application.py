"""Actual bounded scene → PluginManager/Phase9/public boundary regressions."""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from test_plugins import AllowEvaluator
from test_sentry_boundary import _identity
from test_sentry_boundary_hardening import MemoryStore, request_for

from anima_ha.action import (
    ActionExecutionCoordinator,
    InMemoryActionStore,
    InMemoryPendingApprovalStore,
    InMemoryResourceLocker,
    TruthSnapshot,
)
from anima_ha.home_assistant import HAInstanceConfig, home_assistant_manifest
from anima_ha.intelligence import IntelligenceOrigin, IntelligenceRequestFactory
from anima_ha.plugins import NativeRuntime, PluginManager, PluginValidationError, validate_instance
from anima_ha.policy import Assurance, IdentityContext, PolicyContext, PolicyService, RequestOrigin
from anima_ha.scene_application import SceneApplication
from anima_ha.scenes import SCENES_MANIFEST, InMemorySceneStore, Scene, SceneNativePlugin
from anima_ha.sentry_boundary import CoreSentryBoundary, SentryBoundaryError
from anima_ha.ui_runtime import CoreUICommandGateway

POWER = "anima.provider.home-assistant.set_power"
APPLY = "anima.scenes.apply_scene"


class ControlledPolicy(AllowEvaluator):
    decision = "ALLOW"

    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        if document["action_intent"]["semantic_action"] == "set_power":
            return {"decision": self.decision, "reason_code": "ISOLATED", "policy_version": "test"}
        return super().evaluate(document)


class SyntheticPower:
    """Native synthetic actuator only; actual manifest and coordinator retained."""

    def __init__(self) -> None:
        self.definition = replace(
            home_assistant_manifest(
                HAInstanceConfig(uuid4(), "ws://127.0.0.1:9/api/websocket", "isolated")
            ),
            required_secrets=(),
        )
        self.states: dict[UUID, str | None] = {}
        self.calls: list[dict[str, Any]] = []
        self.mode = "verified"
        self.after: Any = None

    def start(self, secret_env: dict[str, str]) -> None:
        assert secret_env == {}

    def stop(self) -> None:
        pass

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": t["name"], "input_schema": t["input_schema"]} for t in self.definition.tools
        ]

    def invoke(
        self, name: str, arguments: dict[str, Any], timeout: float, execution_context: Any = None
    ) -> Any:
        assert name == "set_power" and execution_context is not None
        self.calls.append(dict(arguments))
        resource = UUID(arguments["resource_id"])
        if self.mode == "verified":
            self.states[resource] = "on" if arguments["desired_on"] else "off"
        elif self.mode == "unknown":
            self.states[resource] = None
        if self.after:
            self.after()
        if self.mode == "malformed":
            return "invalid connector output after entry"
        return {"outcome": "SUCCESS"}

    def refresh(self, resources: tuple[UUID, ...]) -> TruthSnapshot:
        return TruthSnapshot(
            {
                f"power:{r}": {
                    "state": "KNOWN" if self.states.get(r) is not None else "UNKNOWN",
                    "value": self.states.get(r),
                    "version": str(len(self.calls)),
                }
                for r in resources
            }
        )


class Harness:
    def __init__(self, *, store: Any = None, action_store: Any = None, locker: Any = None) -> None:
        self.ui = _identity()
        self.identity = IdentityContext(
            self.ui.household_id, self.ui.principal_id, Assurance.AUTHENTICATED
        )
        self.power = SyntheticPower()
        self.manager = PluginManager()
        self.manager.register(
            self.power.definition,
            NativeRuntime(self.power),
            configuration={
                "instance_id": str(uuid4()),
                "websocket_url": "ws://127.0.0.1:9/api/websocket",
            },
        )
        self.manager.enable(self.power.definition.plugin_id)
        self.store = store or InMemorySceneStore()
        self.resources = [uuid4(), uuid4()]
        self.capabilities = {r: uuid4() for r in self.resources}
        self.power.states = dict.fromkeys(self.resources, "off")
        self.valid = True
        self.role = "owner"
        self.policy = ControlledPolicy()
        self.service_policy = PolicyService(self.policy)
        self.manager.register(
            SCENES_MANIFEST, NativeRuntime(SceneNativePlugin(self.store, self.resource_valid))
        )
        self.manager.enable(SCENES_MANIFEST.plugin_id)
        self.scene = self.store.create(
            Scene.create(
                household_id=self.identity.household_id,
                name="Isolated scene",
                steps=[{"resource_id": str(r), "desired_on": True} for r in self.resources],
                creator_principal_id=self.identity.principal_id,
            )
        )
        self.actions = action_store or InMemoryActionStore()
        self.approvals = InMemoryPendingApprovalStore()
        self.executor = ActionExecutionCoordinator(
            self.manager,
            self.actions,
            locker or InMemoryResourceLocker(),
            pending_approvals=self.approvals,
        )
        self.application = SceneApplication(
            self.store,
            self.manager,
            self.executor,
            self.service_policy,
            resource_validator=self.resource_valid,
            authority_validator=lambda i: (
                self.valid
                and i.household_id == self.identity.household_id
                and i.principal_id == self.identity.principal_id
            ),
            policy_context=lambda _: PolicyContext(principal_role=self.role),
            capability_resolver=self.capabilities.get,
            refresher=self.power.refresh,
        )

    def resource_valid(self, household: UUID, resource: UUID) -> bool:
        return self.valid and household == self.identity.household_id and resource in self.resources

    def arguments(self, version: int = 1) -> dict[str, Any]:
        return {"scene_id": str(self.scene.scene_id), "expected_version": version}

    def apply(self, key: str = "bounded-attempt", **kwargs: Any) -> dict[str, Any]:
        return self.application.apply(
            self.arguments(),
            identity=self.identity,
            origin=RequestOrigin.DIRECT_USER,
            idempotency_key=key,
            **kwargs,
        )

    def update(self, enabled: bool = True) -> None:
        self.scene = self.store.update(
            self.identity.household_id,
            self.scene.scene_id,
            self.scene.version,
            name="Revised scene",
            steps=[s.to_payload() for s in self.scene.steps],
            enabled=enabled,
            now=datetime.now(UTC),
        )

    def boundary(self) -> tuple[CoreSentryBoundary, MemoryStore]:
        pending = IntelligenceRequestFactory.for_direct_sentry_interaction(
            sentry_request_id=str(uuid4()),
            household_id=self.identity.household_id,
            source_surface="isolated",
            user_text="Synthetic",
            tools=self.manager.list_tools(),
            service_client_id="isolated",
        )
        request = replace(
            request_for(catalogue=pending.catalogue),
            origin=IntelligenceOrigin.DIRECT_UI_USER,
            principal_id=self.identity.principal_id,
        )
        store = MemoryStore(request)
        return CoreSentryBoundary(
            self.manager,
            self.service_policy,
            cast(Any, store),
            action_executor=self.executor,
            scene_application=self.application,
            access_level_resolver=lambda _: "UNRESTRICTED",
        ), store


def test_verified_shared_ui_and_frozen_mcp_with_terminal_duplicates() -> None:
    h = Harness()
    gateway = CoreUICommandGateway(h.manager, h.service_policy, scene_application=h.application)
    payload = {"expected_version": 1, "attempt_id": str(uuid4())}
    first = gateway.apply_scene(h.ui, str(h.scene.scene_id), payload)
    assert first["status"] == "SUCCEEDED" and len(h.power.calls) == 2
    repeated = gateway.apply_scene(h.ui, str(h.scene.scene_id), payload)
    assert repeated["duplicate"] and repeated["action_id"] == first["action_id"]
    assert repeated["result"] == first["result"] and len(h.power.calls) == 2
    boundary, store = h.boundary()
    result = boundary.invoke_tool(store.request, APPLY, h.arguments(), ordinal=1)
    assert result["status"] == first["status"]
    assert result["result"]["saved_scene"] == first["result"]["saved_scene"]
    assert len(h.power.calls) == 2  # Current state already satisfies both steps.
    assert boundary.invoke_tool(store.request, APPLY, h.arguments(), ordinal=1)["duplicate"]
    validate_instance(
        next(t for t in h.manager.list_tools() if t.tool_id == APPLY).output_schema or {}, result
    )


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("unknown", "UNKNOWN_RESULT"),
        ("unverified", "VERIFICATION_FAILED"),
        ("malformed", "VERIFICATION_FAILED"),
    ],
)
def test_uncertain_or_failed_first_step_stops_and_is_not_replayed(mode: str, expected: str) -> None:
    h = Harness()
    h.power.mode = mode
    result = h.apply()
    assert result["status"] == expected and len(result["result"]["steps"]) == 1
    assert len(h.power.calls) == 1
    h.actions.recover_incomplete()
    assert h.apply()["duplicate"] and len(h.power.calls) == 1


def test_partial_scene_has_actual_child_status_and_no_missing_step_retry() -> None:
    h = Harness()
    h.power.after = lambda: setattr(h.power, "mode", "unknown") if len(h.power.calls) == 1 else None
    result = h.apply()
    assert result["status"] == "PARTIAL"
    assert [s["status"] for s in result["result"]["steps"]] == ["SUCCEEDED", "UNKNOWN_RESULT"]
    assert h.apply()["duplicate"] and len(h.power.calls) == 2


@pytest.mark.parametrize("change", ["scene", "authority", "role", "catalogue", "capability"])
def test_changed_reality_during_first_step_never_starts_second(change: str) -> None:
    h = Harness()

    def mutate() -> None:
        if change == "scene":
            h.update()
        if change == "authority":
            h.valid = False
        if change == "role":
            h.role = "restricted"
        if change == "catalogue":
            h.manager.disable(h.power.definition.plugin_id)
        if change == "capability":
            h.capabilities[h.resources[0]] = uuid4()

    h.power.after = mutate
    result = h.apply()
    assert result["status"] == "UNKNOWN_RESULT"
    assert len(h.power.calls) == 1 and len(result["result"]["steps"]) == 1


@pytest.mark.parametrize("decision", ["DENY", "REQUIRE_STRONGER_AUTH", "REQUIRE_CONFIRMATION"])
def test_policy_gate_before_physical_dispatch(decision: str) -> None:
    h = Harness()
    h.policy.decision = decision
    result = h.apply()
    assert result["status"] == {"DENY": "POLICY_DENIED"}.get(decision, decision)
    assert not h.power.calls and len(result["result"]["steps"]) == 1


def test_stale_or_disabled_scene_and_foreign_resource_are_not_dispatched() -> None:
    h = Harness()
    h.update(False)
    assert h.apply()["status"] == "PRECONDITION_FAILED" and not h.power.calls
    result = h.application.apply(
        h.arguments(2),
        identity=h.identity,
        origin=RequestOrigin.DIRECT_USER,
        idempotency_key="new-disabled",
    )
    assert result["status"] == "PRECONDITION_FAILED" and not h.power.calls
    with pytest.raises(Exception, match="SCENE_AUTHORITY_CHANGED"):
        h.application.apply(
            h.arguments(2),
            identity=replace(h.identity, household_id=uuid4()),
            origin=RequestOrigin.DIRECT_USER,
            idempotency_key="foreign",
        )


def test_idempotency_conflict_never_dispatches_a_changed_saved_version() -> None:
    h = Harness()
    first = h.apply()
    h.update()
    result = h.application.apply(
        h.arguments(2),
        identity=h.identity,
        origin=RequestOrigin.DIRECT_USER,
        idempotency_key="bounded-attempt",
    )
    assert result["reason"] == "SCENE_IDEMPOTENCY_CONFLICT"
    assert len(h.power.calls) == 2 and first["result"]["scene_version"] == 1


def test_request_fencing_and_frozen_catalogue_fail_closed() -> None:
    h = Harness()
    boundary, store = h.boundary()
    stale = store.request
    store.request = replace(stale, fencing_generation=2)
    with pytest.raises(SentryBoundaryError, match="CLAIM_LOST"):
        boundary.invoke_tool(stale, APPLY, h.arguments(), ordinal=1)
    store.request = replace(
        stale, catalogue=tuple(t for t in stale.catalogue if t["tool_id"] != POWER)
    )
    with pytest.raises(SentryBoundaryError, match="TOOL_NOT_BOUND"):
        boundary.invoke_tool(store.request, APPLY, h.arguments(), ordinal=1)
    assert not h.power.calls


def test_direct_plugin_cannot_bypass_verified_scene_composition() -> None:
    h = Harness()
    with pytest.raises(PluginValidationError):
        cast(NativeRuntime, h.manager.plugins[SCENES_MANIFEST.plugin_id].runtime).plugin.invoke(
            "apply_scene", h.arguments(), 1.0
        )


def test_child_confirmation_cannot_apply_disabled_scene_after_restart() -> None:
    h = Harness()
    h.policy.decision = "REQUIRE_CONFIRMATION"
    result = h.apply()
    step = result["result"]["steps"][0]
    approval_id = UUID(step["result"]["approval_id"])
    h.update(False)
    h.policy.decision = "ALLOW"
    gateway = CoreUICommandGateway(
        h.manager,
        h.service_policy,
        action_executor=h.executor,
        action_refresher=h.power.refresh,
        scene_application=h.application,
        policy_role_resolver=lambda _: h.role,
    )
    outcome = gateway.confirmation(h.ui, str(approval_id), "APPROVE")
    assert outcome["status"] != "SUCCEEDED" and not h.power.calls
    assert h.apply()["duplicate"]


def test_crash_retains_plan_and_child_attempt_without_resuming() -> None:
    h = Harness()

    class ProcessCrash(BaseException):
        pass

    h.power.after = lambda: (_ for _ in ()).throw(ProcessCrash())
    with pytest.raises(ProcessCrash):
        h.apply()
    h.actions.recover_incomplete()
    result = h.apply()
    assert result["status"] == "UNKNOWN_RESULT" and result["duplicate"]
    assert result["result"]["saved_scene"]["version"] == 1
    assert len(result["result"]["steps"]) == 1 and len(h.power.calls) == 1


@pytest.mark.parametrize("decision", ["APPROVE", "REJECT"])
def test_existing_child_approval_projects_outcome_without_resuming_scene(decision: str) -> None:
    h = Harness()
    h.policy.decision = "REQUIRE_CONFIRMATION"
    first = h.apply()
    approval_id = UUID(first["result"]["steps"][0]["result"]["approval_id"])
    # Reconstruct the domain guard as production does after restart; no closure
    # from the first call is required by the persisted approval.
    h.executor = ActionExecutionCoordinator(
        h.manager, h.actions, InMemoryResourceLocker(), pending_approvals=h.approvals
    )
    h.application = SceneApplication(
        h.store,
        h.manager,
        h.executor,
        h.service_policy,
        resource_validator=h.resource_valid,
        authority_validator=lambda i: (
            i.household_id == h.identity.household_id
            and i.principal_id == h.identity.principal_id
            and i.assurance == Assurance.AUTHENTICATED
        ),
        policy_context=lambda _: PolicyContext(principal_role=h.role),
        capability_resolver=h.capabilities.get,
        refresher=h.power.refresh,
    )
    h.policy.decision = "ALLOW"
    gateway = CoreUICommandGateway(
        h.manager,
        h.service_policy,
        action_executor=h.executor,
        action_refresher=h.power.refresh,
        scene_application=h.application,
        policy_role_resolver=lambda _: h.role,
    )
    outcome = gateway.confirmation(h.ui, str(approval_id), decision)
    assert outcome["status"] == ("SUCCEEDED" if decision == "APPROVE" else "REJECTED")
    projected = h.apply()
    assert projected["duplicate"] and projected["recorded_status"] == "REQUIRE_CONFIRMATION"
    assert projected["status"] == ("PARTIAL" if decision == "APPROVE" else "POLICY_DENIED")
    assert projected["result"]["steps"][0]["status"] == (
        "SUCCEEDED" if decision == "APPROVE" else "POLICY_DENIED"
    )
    assert len(h.power.calls) == (1 if decision == "APPROVE" else 0)
    assert len(projected["result"]["steps"]) == 1


@pytest.mark.parametrize(
    "change", ["version", "authority", "catalogue", "capability", "guard_missing"]
)
def test_saved_child_approval_revalidates_durable_bindings(change: str) -> None:
    h = Harness()
    h.policy.decision = "REQUIRE_CONFIRMATION"
    first = h.apply()
    approval_id = UUID(first["result"]["steps"][0]["result"]["approval_id"])
    if change == "version":
        h.update()
    elif change == "authority":
        h.valid = False
    elif change == "catalogue":
        h.manager.disable(h.power.definition.plugin_id)
    elif change == "capability":
        h.capabilities[h.resources[0]] = uuid4()
    else:
        h.executor.scene_approval_refresher = None
    h.policy.decision = "ALLOW"
    gateway = CoreUICommandGateway(
        h.manager,
        h.service_policy,
        action_executor=h.executor,
        action_refresher=h.power.refresh,
        scene_application=h.application,
    )
    if change == "catalogue":
        from anima_ha.ui_api import UICommandError

        with pytest.raises(UICommandError, match="CORE_TOOL_UNAVAILABLE"):
            gateway.confirmation(h.ui, str(approval_id), "APPROVE")
        assert not h.power.calls
        return
    result = gateway.confirmation(h.ui, str(approval_id), "APPROVE")
    assert result["status"] != "SUCCEEDED" and not h.power.calls


def test_inflight_duplicate_and_competing_attempt_never_interleave_steps() -> None:
    h = Harness()
    results = []
    h.power.after = lambda: results.extend([h.apply(), h.apply("competing")])
    assert h.apply()["status"] == "SUCCEEDED"
    assert len(h.power.calls) == 2
    assert [r["status"] for r in results[:2]] == ["UNKNOWN_RESULT", "UNKNOWN_RESULT"]
    assert all(r["duplicate"] for r in results)
    assert results[0]["duplicate"]


def test_scene_input_contract_excludes_provider_identity_and_boolean_version() -> None:
    h = Harness()
    for arguments in (
        {**h.arguments(), "entity_id": "light.private"},
        {**h.arguments(), "expected_version": True},
    ):
        with pytest.raises(PluginValidationError):
            h.application.apply(
                arguments,
                identity=h.identity,
                origin=RequestOrigin.DIRECT_USER,
                idempotency_key="invalid",
            )
    assert not h.power.calls and not h.actions.records


def test_fresh_request_after_failed_scene_does_not_blindly_repeat_started_child() -> None:
    h = Harness()
    h.power.mode = "unverified"
    first = h.apply()
    repeated = h.apply("fresh-request-after-browser-reload")
    assert repeated["action_id"] == first["action_id"] and repeated["duplicate"]
    assert len(h.power.calls) == 1
    # A separately saved new definition is not an automatic continuation.
    h.update()
    changed = h.application.apply(
        h.arguments(2),
        identity=h.identity,
        origin=RequestOrigin.DIRECT_USER,
        idempotency_key="explicit-new-saved-version",
    )
    assert changed["action_id"] != first["action_id"]
    assert changed["result"]["saved_scene"]["version"] == 2 and len(h.power.calls) == 2
    interrupted = Harness()
    with pytest.MonkeyPatch.context() as patch:

        def fail(*args: Any) -> Any:
            raise RuntimeError("isolated attempt interrupted before result capture")

        patch.setattr(interrupted.executor, "execute", fail)
        uncertain = interrupted.apply()
    assert uncertain["status"] == "UNKNOWN_RESULT" and not interrupted.power.calls
    assert interrupted.apply("new-key")["action_id"] == uncertain["action_id"]


@pytest.mark.parametrize(
    "assurance", [Assurance.RECOGNIZED, Assurance.AUTHENTICATED, Assurance.STRONG_AUTHENTICATED]
)
def test_approval_guard_receives_actual_current_identity_not_inferred_authority(
    assurance: Assurance,
) -> None:
    h = Harness()
    h.policy.decision = "REQUIRE_CONFIRMATION"
    first = h.apply()
    approval_id = UUID(first["result"]["steps"][0]["result"]["approval_id"])
    h.policy.decision = "ALLOW"
    actual = replace(h.identity, assurance=assurance, evidence_ids=(uuid4(),))
    captured = []
    original = h.application.approval_refresher

    def guard(pending: Any, context: PolicyContext, identity: IdentityContext) -> Any:
        captured.append(identity)
        return original(pending, context, identity)

    h.executor.scene_approval_refresher = guard
    outcome = h.executor.approve_pending(
        approval_id,
        household_id=actual.household_id,
        principal_id=h.ui.principal_id,
        decision="APPROVE",
        tool=next(t for t in h.manager.list_tools() if t.tool_id == POWER),
        policy_service=h.service_policy,
        policy_context=PolicyContext(principal_role="owner"),
        approval_identity=actual,
        refresher=h.power.refresh,
    )
    assert outcome
    if assurance == Assurance.RECOGNIZED:
        assert outcome.record.status.value == "POLICY_DENIED" and not captured and not h.power.calls
    else:
        assert captured == [actual] and captured[0] is actual
        assert outcome.record.status.value == "SUCCEEDED" and len(h.power.calls) == 1
