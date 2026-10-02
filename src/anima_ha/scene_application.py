"""Bounded saved-scene composition; physical work stays in Phase 9.

The aggregate is an existing action record, never a resumable workflow. Its
children are ordinary verified controls with stable, server-owned identities.
No repeat of an aggregate (including an incomplete one) starts another child.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any
from uuid import UUID, uuid5

from anima_ha.action import (
    ActionExecutionCoordinator,
    ActionRecord,
    ActionRequest,
    ActionStatus,
    ActionVerifier,
    PendingApproval,
    TruthRefresher,
    TruthSnapshot,
    resolve_action_safety_spec,
)
from anima_ha.plugins import (
    PluginManager,
    RuntimeKind,
    ToolDescriptor,
    TrustClass,
    validate_instance,
)
from anima_ha.policy import (
    ActionIntent,
    Decision,
    IdentityContext,
    PolicyContext,
    PolicyService,
    RequestOrigin,
)
from anima_ha.scenes import Scene, SceneError


class SceneApplication:
    """Share the existing UI verified sequence with the production boundary."""

    def __init__(
        self,
        store: Any,
        manager: PluginManager,
        executor: ActionExecutionCoordinator,
        policy: PolicyService,
        *,
        resource_validator: Callable[[UUID, UUID], bool],
        authority_validator: Callable[[IdentityContext], bool],
        policy_context: Callable[[IdentityContext], PolicyContext],
        capability_resolver: Callable[[UUID], UUID | None],
        refresher: TruthRefresher | None,
        verifier: ActionVerifier | None = None,
    ) -> None:
        self.store, self.manager, self.executor, self.policy = store, manager, executor, policy
        self.resource_validator, self.authority_validator = resource_validator, authority_validator
        self.policy_context, self.capability_resolver = policy_context, capability_resolver
        self.refresher, self.verifier = refresher, verifier
        self.executor.scene_approval_refresher = self.approval_refresher

    def approval_refresher(
        self, pending: PendingApproval, context: PolicyContext, identity: IdentityContext
    ) -> TruthRefresher:
        """Reconstruct only a scene child's guard, never continue its sequence.

        The reserved idempotency key and aggregate latest_truth are Core-owned
        durable records. Neither is accepted as a model tool argument. A fresh
        owner approval rechecks the saved configuration, not an expired worker
        claim, and authorizes this one existing child through Phase9 as usual.
        """

        def check() -> None:
            _, root_id, raw_index = pending.idempotency_key.split(":")
            index = int(raw_index)
            root = self.executor.store.get(UUID(root_id))
            if (
                root is None
                or root.tool_id != "anima.scenes.apply_scene"
                or root.household_id != pending.household_id
            ):
                raise SceneError("SCENE_APPROVAL_BINDING_UNAVAILABLE")
            binding = root.latest_truth
            if binding.get("principal_id") != str(pending.principal_id):
                raise SceneError("SCENE_AUTHORITY_CHANGED")
            saved = binding["saved_scene"]
            current = self._check(identity, UUID(saved["scene_id"]), saved["version"])
            if current.to_payload() != saved or self.policy_context(identity) != context:
                raise SceneError("SCENE_APPROVAL_CONFIGURATION_CHANGED")
            if (
                index < 1
                or index > len(current.steps)
                or pending.action_id != uuid5(root.action_id, f"step:{index}")
            ):
                raise SceneError("SCENE_APPROVAL_CHILD_CHANGED")
            step = current.steps[index - 1]
            capability = self.capability_resolver(step.resource_id)
            if binding["capability_ids"].get(str(step.resource_id)) != (
                str(capability) if capability else None
            ):
                raise SceneError("SCENE_CAPABILITY_BINDING_CHANGED")
            expected: dict[str, Any] = {
                "resource_id": str(step.resource_id),
                "desired_on": step.desired_on,
            }
            if capability is not None:
                expected["capability_id"] = str(capability)
            if (
                expected != pending.arguments
                or pending.tool_id != "anima.provider.home-assistant.set_power"
            ):
                raise SceneError("SCENE_APPROVAL_ARGUMENTS_CHANGED")
            for tool_id, key in (
                ("anima.scenes.apply_scene", "scene_tool"),
                (pending.tool_id, "power_tool"),
            ):
                if self._tool(tool_id).to_payload() != binding[key]:
                    raise SceneError("SCENE_APPROVAL_CATALOGUE_CHANGED")

        def refresh(resources: tuple[UUID, ...]) -> TruthSnapshot:
            check()
            if self.refresher is None:
                raise SceneError("SCENE_CURRENT_STATE_UNAVAILABLE")
            result = self.refresher(resources)
            check()
            return result

        return refresh

    def _tool(self, tool_id: str) -> ToolDescriptor:
        tool = next((item for item in self.manager.list_tools() if item.tool_id == tool_id), None)
        if tool is None or not tool.availability:
            raise SceneError("SCENE_TOOL_UNAVAILABLE")
        return tool

    def _check(self, identity: IdentityContext, scene_id: UUID, version: int) -> Scene:
        if not self.authority_validator(identity):
            raise SceneError("SCENE_AUTHORITY_CHANGED")
        scene: Scene = self.store.get(identity.household_id, scene_id)
        if scene.version != version or not scene.enabled:
            raise SceneError("SCENE_VERSION_OR_ENABLED_CHANGED")
        if not all(
            self.resource_validator(identity.household_id, step.resource_id) for step in scene.steps
        ):
            raise SceneError("SCENE_RESOURCE_UNAVAILABLE")
        return scene

    def _response(self, record: ActionRecord, *, duplicate: bool = False) -> dict[str, Any]:
        pending = record.status in {ActionStatus.PLANNED, ActionStatus.EXECUTING}
        result = deepcopy(record.result)
        status = ActionStatus.UNKNOWN_RESULT.value if pending else record.status.value
        detail = (
            "existing attempt is not terminal; no additional step dispatched"
            if pending
            else record.detail
        )
        if result:
            approved = False
            for step in result.get("steps", []):
                child = self.executor.store.get(UUID(step["action_id"]))
                if (
                    step["status"] == ActionStatus.REQUIRE_CONFIRMATION.value
                    and child
                    and child.status != ActionStatus.REQUIRE_CONFIRMATION
                ):
                    approved = True
                    step.update(status=child.status.value, detail=child.detail, result=child.result)
            if approved:
                steps = result["steps"]
                if all(s["status"] == ActionStatus.SUCCEEDED.value for s in steps):
                    status = (
                        "SUCCEEDED"
                        if len(steps) == len(result["saved_scene"]["steps"])
                        else "PARTIAL"
                    )
                else:
                    status = (
                        "PARTIAL"
                        if any(s["status"] == "SUCCEEDED" for s in steps)
                        else steps[-1]["status"]
                    )
                detail = "existing approved child outcome projected; no other step dispatched"
        return {
            "status": status,
            "recorded_status": record.status.value,
            "operation": "anima.scenes.apply_scene",
            "action_id": str(record.action_id),
            "duplicate": duplicate,
            "detail": detail,
            "result": result,
        }

    def apply(
        self,
        arguments: dict[str, Any],
        *,
        identity: IdentityContext,
        origin: RequestOrigin,
        idempotency_key: str,
        guard: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        tool = self._tool("anima.scenes.apply_scene")
        plugin = self.manager.plugins[tool.plugin_id]
        if (
            plugin.manifest.source != "builtin:anima_ha.scenes"
            or plugin.manifest.runtime_kind != RuntimeKind.TRUSTED_NATIVE
            or plugin.manifest.trust_class != TrustClass.TRUSTED_NATIVE
        ):
            raise SceneError("SCENE_SOURCE_INVALID")
        validate_instance(tool.input_schema, arguments)
        scene_id, version = UUID(arguments["scene_id"]), arguments["expected_version"]
        if guard is not None:
            guard()
        if not self.authority_validator(identity):
            raise SceneError("SCENE_AUTHORITY_CHANGED")
        # Principal/origin are Core-owned digest fields, not tool arguments.
        root = ActionRequest.create(
            idempotency_key=f"scene:{identity.household_id}:{identity.principal_id}:{idempotency_key}",
            household_id=identity.household_id,
            tool=tool,
            arguments={
                **arguments,
                "principal_id": str(identity.principal_id),
                "origin": origin.value,
            },
            identity=identity,
            policy_service=self.policy,
        )
        previous = self.executor.store.latest_scene_application(identity.household_id, scene_id)
        if previous is not None and previous.idempotency_key != root.idempotency_key:
            try:
                self._check(identity, scene_id, version)
            except SceneError as exc:
                return {
                    "status": "PRECONDITION_FAILED",
                    "operation": tool.tool_id,
                    "reason": str(exc),
                }
            response = self._response(previous, duplicate=True)
            # An explicitly saved new version is a new configuration/intent,
            # not a continuation of the old sequence. Its own apply still
            # performs all current identity/policy/truth/lock checks.
            if previous.latest_truth["saved_scene"]["version"] == version and response[
                "status"
            ] in {
                "PLANNED",
                "EXECUTING",
                "UNKNOWN_RESULT",
                "PARTIAL",
                "FAILED",
                "VERIFICATION_FAILED",
                "RECOVERY_REQUIRED",
                "REQUIRE_CONFIRMATION",
            }:
                response["detail"] = (
                    "previous attempt of this saved version unresolved; "
                    "returning existing outcomes; "
                    "no new or remaining step dispatched"
                )
                response["reason"] = "SCENE_PREVIOUS_ATTEMPT_UNRESOLVED"
                return response
        claim = self.executor.store.claim(root)
        if claim.idempotency_conflict:
            return {
                "status": "PRECONDITION_FAILED",
                "operation": tool.tool_id,
                "reason": "SCENE_IDEMPOTENCY_CONFLICT",
            }
        if claim.duplicate:
            return self._response(claim.record, duplicate=True)
        progress: dict[str, Any] = {
            "scene_id": str(scene_id),
            "scene_version": version,
            "steps": [],
        }

        def finish(status: ActionStatus, detail: str) -> dict[str, Any]:
            record = self.executor.store.update(
                root.action_id, status, detail=detail, result=deepcopy(progress)
            )
            return self._response(record)

        with self.executor.locker.try_acquire(
            (f"scene:{identity.household_id}:{scene_id}",)
        ) as acquired:
            if not acquired:
                return finish(
                    ActionStatus.RESOURCE_BUSY, "another scene attempt owns this saved scene"
                )
            try:
                scene = self._check(identity, scene_id, version)
                context = self.policy_context(identity)
                decision = self.policy.evaluate(
                    ActionIntent.create(
                        household_id=identity.household_id,
                        principal_id=identity.principal_id,
                        semantic_action=tool.semantic_action,
                        origin=origin,
                        graph_metadata={
                            "plugin_id": tool.plugin_id,
                            "read_only": False,
                            "writable": True,
                        },
                    ),
                    identity,
                    context,
                )
                if decision.decision != Decision.ALLOW:
                    return finish(
                        {
                            Decision.DENY: ActionStatus.POLICY_DENIED,
                            Decision.REQUIRE_CONFIRMATION: ActionStatus.REQUIRE_CONFIRMATION,
                            Decision.REQUIRE_STRONGER_AUTH: ActionStatus.REQUIRE_STRONGER_AUTH,
                        }[decision.decision],
                        decision.reason_code,
                    )
                power = self._tool("anima.provider.home-assistant.set_power")
                capabilities = {
                    str(step.resource_id): self.capability_resolver(step.resource_id)
                    for step in scene.steps
                }
                progress["saved_scene"] = scene.to_payload()
                progress["power_tool_version"] = power.version
                self.executor.store.update(
                    root.action_id,
                    ActionStatus.EXECUTING,
                    detail="applying immutable saved scene through verified controls",
                    result=deepcopy(progress),
                    latest_truth={
                        "saved_scene": scene.to_payload(),
                        "principal_id": str(identity.principal_id),
                        "scene_tool": tool.to_payload(),
                        "power_tool": power.to_payload(),
                        "capability_ids": {
                            key: str(value) if value else None
                            for key, value in capabilities.items()
                        },
                    },
                )
                for index, step in enumerate(scene.steps, start=1):
                    child_context = self.policy_context(identity)

                    def check_binding(
                        resource_id: UUID = step.resource_id,
                        expected_context: PolicyContext = child_context,
                    ) -> None:
                        if guard is not None:
                            guard()
                        if (
                            self._check(identity, scene_id, version).to_payload()
                            != scene.to_payload()
                        ):
                            raise SceneError("SCENE_CONFIGURATION_CHANGED")
                        if self._tool(tool.tool_id).to_payload() != tool.to_payload():
                            raise SceneError("SCENE_BINDING_CHANGED")
                        if self.capability_resolver(resource_id) != capabilities[str(resource_id)]:
                            raise SceneError("SCENE_CAPABILITY_BINDING_CHANGED")
                        current = self._tool(power.tool_id)
                        if current.to_payload() != power.to_payload():
                            raise SceneError("SCENE_POWER_BINDING_CHANGED")
                        if self.policy_context(identity) != expected_context:
                            raise SceneError("SCENE_POLICY_CONTEXT_CHANGED")

                    def refresh(
                        resources: tuple[UUID, ...],
                        check: Callable[[], None] = check_binding,
                    ) -> TruthSnapshot:
                        check()
                        if self.refresher is None:
                            raise SceneError("SCENE_CURRENT_STATE_UNAVAILABLE")
                        snapshot = self.refresher(resources)
                        check()
                        return snapshot

                    check_binding()
                    child_arguments: dict[str, Any] = {
                        "resource_id": str(step.resource_id),
                        "desired_on": step.desired_on,
                    }
                    capability_id = capabilities[str(step.resource_id)]
                    if capability_id is not None:
                        child_arguments["capability_id"] = str(capability_id)
                    child = ActionRequest.create(
                        action_id=uuid5(root.action_id, f"step:{index}"),
                        idempotency_key=f"scene-step:{root.action_id}:{index}",
                        household_id=identity.household_id,
                        tool=power,
                        arguments=child_arguments,
                        identity=identity,
                        policy_service=self.policy,
                        policy_context=child_context,
                        refresher=refresh,
                        verifier=self.verifier,
                        origin=origin,
                        safety_spec=resolve_action_safety_spec(power),
                    )
                    progress["steps"].append(
                        {
                            "step": index,
                            "resource_id": str(step.resource_id),
                            "action_id": str(child.action_id),
                            "status": "PLANNED",
                            "detail": "child outcome not yet confirmed",
                            "result": None,
                        }
                    )
                    self.executor.store.update(
                        root.action_id, ActionStatus.EXECUTING, result=deepcopy(progress)
                    )
                    execution = self.executor.execute(child)
                    progress["steps"][-1].update(
                        status=execution.record.status.value,
                        detail=execution.record.detail,
                        result=execution.record.result,
                    )
                    self.executor.store.update(
                        root.action_id, ActionStatus.EXECUTING, result=deepcopy(progress)
                    )
                    if execution.record.status != ActionStatus.SUCCEEDED:
                        status = ActionStatus.PARTIAL if index > 1 else execution.record.status
                        return finish(
                            status, f"scene stopped at step {index}; remaining steps not started"
                        )
                return finish(
                    ActionStatus.SUCCEEDED, "all saved scene steps independently verified"
                )
            except SceneError as exc:
                status = (
                    ActionStatus.PARTIAL
                    if any(step["status"] == "SUCCEEDED" for step in progress["steps"])
                    else ActionStatus.UNKNOWN_RESULT
                    if progress["steps"]
                    else ActionStatus.PRECONDITION_FAILED
                )
                return finish(status, str(exc))
            except Exception as exc:
                status = (
                    ActionStatus.PARTIAL
                    if any(step["status"] == "SUCCEEDED" for step in progress["steps"])
                    else ActionStatus.UNKNOWN_RESULT
                )
                return finish(
                    status, f"scene interrupted: {type(exc).__name__}; no automatic continuation"
                )
