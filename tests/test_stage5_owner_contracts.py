"""Owner transport uses the same finite output schemas as frozen Core tools."""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaValidationError
from pydantic import ValidationError
from test_capability_management import StatusPlugin, optional_manifest

from anima_ha.capability_management import (
    CAPABILITY_MANAGEMENT_MANIFEST,
    CapabilityManagementNativePlugin,
)
from anima_ha.owner_contracts import TaskView, plugin_output_schema
from anima_ha.plugins import NativeRuntime, PluginManager
from anima_ha.policy import Assurance, IdentityContext, PolicyService
from anima_ha.sentry_boundary import CoreSentryBoundary
from anima_ha.ui_api import DemoHouseholdReadModel, UIConfig, UIService, create_app
from anima_ha.ui_runtime import _safe_result


class Allow:
    def evaluate(self, document: Any) -> dict[str, Any]:
        return {"decision": "ALLOW", "reason_code": "TEST", "policy_version": "test"}


class Broken(StatusPlugin):
    def start(self, secret_env: dict[str, str]) -> None:
        raise RuntimeError("private error must not escape")


@pytest.mark.parametrize("registered", [False, True])
def test_failed_or_unavailable_enable_is_not_succeeded(registered: bool) -> None:
    manager = PluginManager()
    if registered:
        manager.register(optional_manifest(), NativeRuntime(Broken()))
    manager.register(
        CAPABILITY_MANAGEMENT_MANIFEST, NativeRuntime(CapabilityManagementNativePlugin(manager))
    )
    manager.enable(CAPABILITY_MANAGEMENT_MANIFEST.plugin_id)
    identity = IdentityContext(uuid4(), uuid4(), Assurance.AUTHENTICATED)
    invocation = manager.invoke(
        "anima.capability-management.set_integration_enabled",
        {"plugin_id": "anima.external.weather", "enabled": True},
        household_id=identity.household_id,
        identity=identity,
        policy_service=PolicyService(Allow()),
    )
    assert invocation.outcome == "SUCCESS"  # transport/schema, not workflow verdict
    for project in (_safe_result, CoreSentryBoundary._safe_invocation):
        public = project(invocation)
        assert public["status"] == ("FAILED" if registered else "UNAVAILABLE")
        assert public["dispatch_state"] == "ACKNOWLEDGED"
        assert "private error" not in str(public)


def test_shared_contract_preserves_extensions_and_failed_task_state() -> None:
    payload = {
        "task_id": "task",
        "title": "t",
        "status": "FAILED",
        "provenance": {"origin": "TESTING"},
    }
    assert TaskView.model_validate(payload).model_dump(exclude_unset=True) == payload
    schema = plugin_output_schema(TaskView)
    assert "$ref" not in str(schema)
    Draft202012Validator(schema).validate(payload)
    with pytest.raises(ValidationError):
        TaskView.model_validate({**payload, "status": "INVENTED_SUCCESS"})


def test_openapi_and_actual_read_response_shapes_match_without_auth_bypass() -> None:
    service = UIService(
        config=UIConfig(test_auth_enabled=True), read_model=DemoHouseholdReadModel()
    )
    app = create_app(service)
    document = app.openapi()
    for path in ("tasks", "calendar", "settings", "preferences", "capabilities", "integrations"):
        operation = document["paths"][f"/api/v1/{path}"]["get"]
        schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
        assert "$ref" in schema
    for path in ("tasks", "calendar", "preferences/{operation}"):
        operation = document["paths"][f"/api/v1/{path}"]["post"]
        assert operation["responses"]["200"]["content"]["application/json"]["schema"]["properties"][
            "status"
        ]["enum"]
        body = operation["requestBody"]["content"]["application/json"]["schema"]
        assert body["properties"]["payload"]["anyOf"]
    settings_body = document["paths"]["/api/v1/settings"]["put"]["requestBody"]["content"][
        "application/json"
    ]["schema"]["properties"]["payload"]
    assert "required" not in settings_body  # existing partial-settings/default contract
    assert settings_body["properties"]["accent"]["enum"]
    integration = document["paths"]["/api/v1/integrations/{operation}"]["post"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]
    Draft202012Validator(integration).validate(
        {
            "status": "UNKNOWN_RESULT",
            "operation": "anima.provider.home-assistant.reconnect",
            "result": {"provider_extension": "retained"},
        }
    )
    with pytest.raises(SchemaValidationError):
        Draft202012Validator(integration).validate(
            {
                "status": "SUCCEEDED",
                "operation": "anima.capability-management.set_integration_enabled",
                "result": {"missing_integration_contract": True},
            }
        )
    with TestClient(app) as client:
        assert client.get("/api/v1/settings").status_code == 401
        client.get("/auth/login")  # explicitly isolated test identity, never owner deployment
        for path in (
            "tasks",
            "calendar",
            "settings",
            "preferences",
            "capabilities",
            "integrations",
        ):
            assert client.get(f"/api/v1/{path}").status_code == 200
