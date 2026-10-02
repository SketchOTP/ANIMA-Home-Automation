"""Shared owner/Core/MCP data contracts, not a second domain model or store.

Domain services still own identity, validation, authority and persistence.
Extension fields are preserved; typed projections never discard legitimate data.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class OwnerRecord(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)


class TaskView(OwnerRecord):
    task_id: str
    title: str
    status: Literal["ACTIVE", "PAUSED", "CANCELLED", "COMPLETED", "FAILED"]
    next_run_at: str | None = None
    latest_run: dict[str, Any] | None = None


class CalendarView(OwnerRecord):
    event_id: str
    title: str
    start_at: str
    end_at: str
    status: Literal["ACTIVE", "CANCELLED"]
    version: int = Field(ge=1)


class PreferenceView(OwnerRecord):
    preference_id: str
    content: str
    category: str
    created_at: str
    status: Literal["ACTIVE", "SUPERSEDED", "RETRACTED", "EXPIRED"]
    scope: Literal["personal", "household"]
    person_id: str | None
    version: str
    authority: Literal["NONE"]


class IntegrationView(OwnerRecord):
    plugin_id: str
    name: str
    description: str
    state: str
    enabled: bool
    capabilities: list[str]
    manageable: bool
    error: str | None = None
    health: dict[str, Any] | None = None


class CapabilityView(OwnerRecord):
    id: str
    label: str
    state: Literal["available", "unavailable", "degraded"]
    detail: str | None = None


class TaskPage(OwnerRecord):
    items: list[TaskView]
    next_cursor: str | None


class CalendarPage(OwnerRecord):
    items: list[CalendarView]
    next_cursor: str | None


class PreferencePage(OwnerRecord):
    items: list[PreferenceView]
    next_cursor: str | None
    members: list[dict[str, Any]]
    can_edit: bool


class IntegrationList(OwnerRecord):
    items: list[IntegrationView]


class CapabilityList(OwnerRecord):
    items: list[CapabilityView]


class InterfaceSettings(OwnerRecord):
    version: int = Field(ge=1)
    appearance: Literal["system", "light", "night"]
    accent: Literal["ember", "sage", "sky", "purple"]
    density: Literal["comfortable", "compact"]
    reduced_motion: bool
    text_scale: Literal["small", "normal", "large"]
    display_mode: Literal["wall", "tablet", "phone", "desktop"]
    visible_widgets: list[str]
    widget_order: list[str]


class SettingsResponse(OwnerRecord):
    settings: InterfaceSettings


class TaskResult(OwnerRecord):
    task: TaskView


class TaskListResult(OwnerRecord):
    tasks: list[TaskView]


class CalendarResult(OwnerRecord):
    event: CalendarView


class CalendarListResult(OwnerRecord):
    events: list[CalendarView]


class PreferenceResult(OwnerRecord):
    status: Literal["SUCCEEDED"]
    preference: PreferenceView


class PreferenceListResult(OwnerRecord):
    status: Literal["SUCCEEDED"]
    items: list[PreferenceView]
    next_cursor: str | None


class IntegrationResult(OwnerRecord):
    status: Literal["SUCCEEDED", "FAILED", "UNAVAILABLE"]
    plugin_id: str
    integration: IntegrationView
    reason: str | None = None


def plugin_output_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Inline only our finite local model definitions; keep plugin $ref forbidden."""
    raw = model.model_json_schema()
    definitions = raw.get("$defs", {})

    def inline(value: Any, active: frozenset[str] = frozenset()) -> Any:
        if isinstance(value, list):
            return [inline(item, active) for item in value]
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            name = str(value["$ref"]).removeprefix("#/$defs/")
            if name not in definitions or name in active:
                raise ValueError("unsupported owner contract reference")
            return inline(
                {
                    **definitions[name],
                    **{key: item for key, item in value.items() if key != "$ref"},
                },
                active | {name},
            )
        return {key: inline(item, active) for key, item in value.items() if key != "$defs"}

    result: dict[str, Any] = inline(raw)
    return result


def command_responses(result_schema: dict[str, Any]) -> dict[int | str, dict[str, Any]]:
    """Describe the existing envelope with the exact plugin's result contract.

    No duplicated request authority or success promotion. Failed pre-dispatch
    responses omit result; typed plugin payload validation happens at invocation.
    """
    from anima_ha.plugins import DispatchState, InvocationOutcome

    schema = {
        "type": "object",
        "required": ["status", "operation"],
        "properties": {
            "status": {
                "enum": [
                    "SUCCEEDED",
                    "FAILED",
                    "DENIED",
                    "UNAVAILABLE",
                    "UNKNOWN_RESULT",
                    "PARTIAL",
                    "REQUIRE_CONFIRMATION",
                    "REQUIRE_STRONGER_AUTH",
                ]
            },
            "operation": {"type": "string"},
            "connector_outcome": {"enum": [item.value for item in InvocationOutcome]},
            "dispatch_state": {"enum": [item.value for item in DispatchState]},
            "result": {"anyOf": [result_schema, {"type": "null"}]},
            "reason": {"type": ["string", "null"]},
            "policy": {"type": "string"},
        },
        "additionalProperties": True,
    }
    # References inside a reused model schema remain rooted at the document.
    schema["$defs"] = result_schema.get("$defs", {})
    return {
        200: {
            "description": "Bounded workflow result; HTTP acceptance is not verified success",
            "content": {"application/json": {"schema": schema}},
        },
        401: {"description": "Authenticated owner session required"},
        403: {"description": "Same-origin/CSRF or authority rejected"},
        404: {"description": "Unsupported operation"},
        503: {"description": "Current Core capability unavailable"},
    }
