"""ANIMA-owned plugin, capability, and tool boundary.

This module owns plugin identity, lifecycle, tool normalization, schema limits,
policy gating, secret scoping, and event ingress. MCP is only a replaceable
transport implementation; plugin metadata never becomes policy authority.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import inspect
import json
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID, uuid4

import psycopg
from jsonschema import Draft202012Validator, SchemaError, ValidationError
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from psycopg.rows import dict_row

from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.policy import (
    ActionIntent,
    Decision,
    IdentityContext,
    PolicyContext,
    PolicyDecision,
    PolicyService,
    RequestOrigin,
)


class PluginValidationError(ValueError):
    """A manifest, schema, collision, or compatibility error."""


class RuntimeKind(StrEnum):
    TRUSTED_NATIVE = "TRUSTED_NATIVE"
    MCP_STDIO = "MCP_STDIO"
    MCP_STREAMABLE_HTTP = "MCP_STREAMABLE_HTTP"


class TrustClass(StrEnum):
    TRUSTED_NATIVE = "TRUSTED_NATIVE"
    OPTIONAL_EXTERNAL = "OPTIONAL_EXTERNAL"


class PluginState(StrEnum):
    DISCOVERED = "DISCOVERED"
    REGISTERED = "REGISTERED"
    DISABLED = "DISABLED"
    STARTING = "STARTING"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    INCOMPATIBLE = "INCOMPATIBLE"
    STOPPING = "STOPPING"


class InvocationOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    PLUGIN_UNAVAILABLE = "PLUGIN_UNAVAILABLE"
    PLUGIN_TIMEOUT = "PLUGIN_TIMEOUT"
    PLUGIN_ERROR = "PLUGIN_ERROR"
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
    INVALID_RESULT = "INVALID_RESULT"
    POLICY_DENIED = "POLICY_DENIED"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"
    REQUIRE_STRONGER_AUTH = "REQUIRE_STRONGER_AUTH"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    UNKNOWN_RESULT = "UNKNOWN_RESULT"


class DispatchState(StrEnum):
    BEFORE_DISPATCH = "BEFORE_DISPATCH"
    POSSIBLY_DISPATCHED = "POSSIBLY_DISPATCHED"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class ExecutionBoundary(StrEnum):
    """ANIMA-owned authority boundary for a normalized tool descriptor."""

    READ_ONLY = "READ_ONLY"
    POLICY_GATED_INTERNAL = "POLICY_GATED_INTERNAL"
    COORDINATED_CONSEQUENTIAL = "COORDINATED_CONSEQUENTIAL"


class ContentPersistence(StrEnum):
    """Core-owned policy for provider-content durability."""

    FULL_DURABLE = "FULL_DURABLE"
    EPHEMERAL_RESTRICTED = "EPHEMERAL_RESTRICTED"


@dataclass(frozen=True, slots=True)
class ProviderExecutionContext:
    """ANIMA-owned execution identity passed only across the provider boundary."""

    execution_id: UUID
    anima_idempotency_key: str
    provider_idempotency_key: str | None = None
    attempt_number: int = 1
    possible_prior_dispatch: bool = False


@dataclass(frozen=True, slots=True)
class InvocationContext:
    """Trusted per-tool provenance generated outside model-controlled arguments."""

    household_id: UUID
    principal_id: UUID | None
    episode_id: UUID | None
    tool_request_id: UUID
    ordinal: int
    system_idempotency_key: str
    origin: RequestOrigin

    def __post_init__(self) -> None:
        if self.ordinal < 1:
            raise PluginValidationError("invocation ordinal must be positive")
        if not self.system_idempotency_key.strip():
            raise PluginValidationError("system idempotency key is required")
        object.__setattr__(self, "origin", RequestOrigin(self.origin))


class ExternalContentTrust(StrEnum):
    LOCAL_TRUSTED = "LOCAL_TRUSTED"
    PLUGIN_TRUSTED = "PLUGIN_TRUSTED"
    EXTERNAL_UNTRUSTED = "EXTERNAL_UNTRUSTED"


class Idempotency(StrEnum):
    NONE = "NONE"
    IDEMPOTENT = "IDEMPOTENT"
    KEYED = "KEYED"


CORE_VERSION = "0.1.0"
MANIFEST_VERSION = 1
ENTRY_POINT_GROUP = "anima_ha.plugins"
MAX_SCHEMA_BYTES = 32_768
MAX_SCHEMA_DEPTH = 8


def _json(value: Any) -> Any:
    json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def _depth(value: Any, level: int = 0) -> int:
    if isinstance(value, dict):
        return max([level] + [_depth(item, level + 1) for item in value.values()])
    if isinstance(value, list):
        return max([level] + [_depth(item, level + 1) for item in value])
    return level


def validate_json_schema(schema: dict[str, Any]) -> None:
    raw = json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
    if len(raw) > MAX_SCHEMA_BYTES or _depth(schema) > MAX_SCHEMA_DEPTH:
        raise PluginValidationError("schema exceeds ANIMA size/depth bounds")
    if "$ref" in raw.decode("utf-8"):
        raise PluginValidationError("remote or local $ref is not permitted in plugin schemas")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise PluginValidationError(f"invalid JSON Schema: {exc.message}") from exc


def validate_instance(schema: dict[str, Any], value: Any) -> None:
    try:
        Draft202012Validator(schema).validate(value)
    except ValidationError as exc:
        raise PluginValidationError(exc.message) from exc


@dataclass(frozen=True, slots=True)
class PluginManifest:
    plugin_id: str
    plugin_version: str
    manifest_version: int
    requires_core: str
    name: str
    description: str
    runtime_kind: RuntimeKind
    trust_class: TrustClass
    capabilities: tuple[str, ...]
    tools: tuple[dict[str, Any], ...]
    events: tuple[str, ...] = ()
    configuration_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object"})
    required_secrets: tuple[str, ...] = ()
    network_requirements: tuple[str, ...] = ("none",)
    risk_metadata: dict[str, Any] = field(default_factory=dict)
    healthcheck: dict[str, Any] = field(default_factory=dict)
    timeouts: dict[str, float] = field(default_factory=dict)
    restart_policy: dict[str, Any] = field(default_factory=dict)
    source: str = "local"

    def __post_init__(self) -> None:
        if self.manifest_version != MANIFEST_VERSION:
            raise PluginValidationError("unsupported manifest version")
        if not self.plugin_id.startswith("anima.") or not self.plugin_id.strip():
            raise PluginValidationError("plugin_id must be a stable anima.* namespace")
        if not self.plugin_version or not self.name.strip():
            raise PluginValidationError("plugin identity and name are required")
        if (
            self.runtime_kind == RuntimeKind.TRUSTED_NATIVE
            and self.trust_class != TrustClass.TRUSTED_NATIVE
        ):
            raise PluginValidationError("native plugins must be TRUSTED_NATIVE")
        if (
            self.runtime_kind != RuntimeKind.TRUSTED_NATIVE
            and self.trust_class == TrustClass.TRUSTED_NATIVE
        ):
            raise PluginValidationError("external runtimes cannot claim native trust")
        validate_json_schema(self.configuration_schema)
        tool_names = [str(tool.get("name", "")) for tool in self.tools]
        if any(not name.strip() for name in tool_names) or len(set(tool_names)) != len(tool_names):
            raise PluginValidationError("duplicate or empty tool names")
        for tool in self.tools:
            validate_json_schema(dict(tool.get("input_schema", {"type": "object"})))
            if "output_schema" in tool and tool["output_schema"] is not None:
                validate_json_schema(dict(tool["output_schema"]))
        if len(set(self.capabilities)) != len(self.capabilities) or len(set(self.events)) != len(
            self.events
        ):
            raise PluginValidationError("duplicate capability or event declaration")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PluginManifest:
        required = {
            "plugin_id",
            "plugin_version",
            "manifest_version",
            "requires_core",
            "name",
            "description",
            "runtime_kind",
            "trust_class",
            "capabilities",
            "tools",
        }
        missing = required - value.keys()
        if missing:
            raise PluginValidationError(f"manifest missing fields: {sorted(missing)}")
        return cls(
            plugin_id=str(value["plugin_id"]),
            plugin_version=str(value["plugin_version"]),
            manifest_version=int(value["manifest_version"]),
            requires_core=str(value["requires_core"]),
            name=str(value["name"]),
            description=str(value["description"]),
            runtime_kind=RuntimeKind(value["runtime_kind"]),
            trust_class=TrustClass(value["trust_class"]),
            capabilities=tuple(str(x) for x in value["capabilities"]),
            tools=tuple(dict(x) for x in value["tools"]),
            events=tuple(str(x) for x in value.get("events", [])),
            configuration_schema=dict(value.get("configuration_schema", {"type": "object"})),
            required_secrets=tuple(str(x) for x in value.get("required_secrets", [])),
            network_requirements=tuple(str(x) for x in value.get("network_requirements", ["none"])),
            risk_metadata=dict(value.get("risk_metadata", {})),
            healthcheck=dict(value.get("healthcheck", {})),
            timeouts={str(k): float(v) for k, v in dict(value.get("timeouts", {})).items()},
            restart_policy=dict(value.get("restart_policy", {})),
            source=str(value.get("source", "local")),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "plugin_version": self.plugin_version,
            "manifest_version": self.manifest_version,
            "requires_core": self.requires_core,
            "name": self.name,
            "description": self.description,
            "runtime_kind": self.runtime_kind.value,
            "trust_class": self.trust_class.value,
            "capabilities": list(self.capabilities),
            "tools": list(self.tools),
            "events": list(self.events),
            "configuration_schema": self.configuration_schema,
            "required_secrets": list(self.required_secrets),
            "network_requirements": list(self.network_requirements),
            "risk_metadata": self.risk_metadata,
            "healthcheck": self.healthcheck,
            "timeouts": self.timeouts,
            "restart_policy": self.restart_policy,
            "source": self.source,
        }


_TRUSTED_INTERNAL_TOOL_IDS = frozenset(
    {
        "anima.durable-tasks.schedule",
        "anima.durable-tasks.cancel",
        "anima.durable-tasks.pause",
        "anima.durable-tasks.resume",
        "anima.calendar.create_event",
        "anima.calendar.update_event",
        "anima.calendar.cancel_event",
    }
)


def _core_execution_boundary(
    manifest: PluginManifest, name: str, item: dict[str, Any]
) -> ExecutionBoundary:
    """Normalize authority in Core; raw plugin metadata cannot lower it."""
    tool_id = f"{manifest.plugin_id}.{name}"
    if tool_id in _TRUSTED_INTERNAL_TOOL_IDS:
        if (
            manifest.runtime_kind == RuntimeKind.TRUSTED_NATIVE
            and manifest.trust_class == TrustClass.TRUSTED_NATIVE
            and manifest.source in {"builtin:anima_ha.tasks", "builtin:anima_ha.calendar"}
        ):
            return ExecutionBoundary.POLICY_GATED_INTERNAL
        return ExecutionBoundary.COORDINATED_CONSEQUENTIAL
    if bool(item.get("read_only", False)):
        return ExecutionBoundary.READ_ONLY
    return ExecutionBoundary.COORDINATED_CONSEQUENTIAL


_CORE_RESTRICTED_CONTENT_TOOL_IDS = frozenset(
    {
        # Best Buy's terms restrict Content retention.  This mapping is
        # deliberately Core-owned; plugin metadata cannot opt into durability.
        "anima.external.shopping.search_products",
        "anima.external.shopping.bestbuy.search_products",
        "anima.external.shopping.upcitemdb.search_products",
    }
)


def _core_content_persistence(manifest: PluginManifest, name: str) -> ContentPersistence:
    tool_id = f"{manifest.plugin_id}.{name}"
    if tool_id in _CORE_RESTRICTED_CONTENT_TOOL_IDS:
        return ContentPersistence.EPHEMERAL_RESTRICTED
    return ContentPersistence.FULL_DURABLE


def core_content_persistence(tool_id: str) -> ContentPersistence:
    """Resolve durability from ANIMA-owned identity, not plugin declarations."""
    return (
        ContentPersistence.EPHEMERAL_RESTRICTED
        if tool_id in _CORE_RESTRICTED_CONTENT_TOOL_IDS
        else ContentPersistence.FULL_DURABLE
    )


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    tool_id: str
    plugin_id: str
    capability_id: str
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None
    risk_class: str
    semantic_action: str
    read_only: bool
    idempotency: Idempotency
    timeout: float
    verification_requirement: str
    external_content_trust: ExternalContentTrust
    availability: bool
    version: str
    provenance: str
    applies_to_node_kinds: tuple[str, ...] = ()
    applies_to_capabilities: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    execution_spec: dict[str, Any] = field(default_factory=dict)
    execution_boundary: ExecutionBoundary | None = None
    content_persistence: ContentPersistence = ContentPersistence.FULL_DURABLE

    def __post_init__(self) -> None:
        boundary = self.execution_boundary
        if boundary is None:
            boundary = (
                ExecutionBoundary.READ_ONLY
                if self.read_only
                else ExecutionBoundary.COORDINATED_CONSEQUENTIAL
            )
        object.__setattr__(self, "execution_boundary", ExecutionBoundary(boundary))

    @classmethod
    def from_manifest(
        cls, manifest: PluginManifest, item: dict[str, Any], *, available: bool = False
    ) -> ToolDescriptor:
        name = str(item["name"])
        risk = str(
            item.get(
                "risk_class", manifest.risk_metadata.get(name, {}).get("risk_class", "UNKNOWN")
            )
        )
        return cls(
            tool_id=f"{manifest.plugin_id}.{name}",
            plugin_id=manifest.plugin_id,
            capability_id=str(
                item.get(
                    "capability_id",
                    manifest.capabilities[0] if manifest.capabilities else "unknown",
                )
            ),
            name=name,
            description=str(item.get("description", manifest.description)),
            input_schema=dict(item.get("input_schema", {"type": "object"})),
            output_schema=dict(item["output_schema"])
            if item.get("output_schema") is not None
            else None,
            risk_class=risk,
            semantic_action=str(item.get("semantic_action", name)),
            read_only=bool(item.get("read_only", False)),
            idempotency=Idempotency(item.get("idempotency", "NONE")),
            timeout=float(item.get("timeout", manifest.timeouts.get("tool", 5.0))),
            verification_requirement=str(item.get("verification_requirement", "NONE")),
            external_content_trust=ExternalContentTrust(
                item.get("external_content_trust", "PLUGIN_TRUSTED")
            ),
            availability=available,
            version=manifest.plugin_version,
            provenance=manifest.source,
            applies_to_node_kinds=tuple(
                str(value) for value in item.get("applies_to_node_kinds", [])
            ),
            applies_to_capabilities=tuple(
                str(value) for value in item.get("applies_to_capabilities", [])
            ),
            tags=tuple(str(value) for value in item.get("tags", [])),
            execution_spec=dict(item.get("execution_spec", {})),
            execution_boundary=_core_execution_boundary(manifest, name, item),
            content_persistence=core_content_persistence(f"{manifest.plugin_id}.{name}"),
        )

    def to_payload(self) -> dict[str, Any]:
        boundary = self.execution_boundary
        assert boundary is not None
        return {
            "tool_id": self.tool_id,
            "plugin_id": self.plugin_id,
            "capability_id": self.capability_id,
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "risk_class": self.risk_class,
            "semantic_action": self.semantic_action,
            "read_only": self.read_only,
            "idempotency": self.idempotency.value,
            "timeout": self.timeout,
            "verification_requirement": self.verification_requirement,
            "external_content_trust": self.external_content_trust.value,
            "availability": self.availability,
            "version": self.version,
            "provenance": self.provenance,
            "applies_to_node_kinds": list(self.applies_to_node_kinds),
            "applies_to_capabilities": list(self.applies_to_capabilities),
            "tags": list(self.tags),
            "execution_spec": self.execution_spec,
            "execution_boundary": boundary.value,
            "content_persistence": self.content_persistence.value,
        }


class PluginRuntime(Protocol):
    def start(self, secret_env: dict[str, str]) -> None: ...
    def stop(self) -> None: ...
    def list_tools(self) -> list[dict[str, Any]]: ...
    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any: ...


class EventSink(Protocol):
    def append(self, event: EventEnvelope) -> Any: ...


class NativePlugin(Protocol):
    def list_tools(self) -> list[dict[str, Any]]: ...
    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any: ...

    def start(self, secret_env: dict[str, str]) -> None: ...
    def stop(self) -> None: ...


class NativeRuntime:
    def __init__(self, plugin: NativePlugin) -> None:
        self.plugin = plugin

    def start(self, secret_env: dict[str, str]) -> None:
        self.plugin.start(secret_env)

    def stop(self) -> None:
        self.plugin.stop()

    def list_tools(self) -> list[dict[str, Any]]:
        return self.plugin.list_tools()

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        return self.plugin.invoke(name, arguments, timeout)

    def invoke_for_household(
        self, name: str, arguments: dict[str, Any], timeout: float, household_id: UUID
    ) -> Any:
        """Pass ANIMA-owned household scope to trusted native capabilities."""
        method = getattr(self.plugin, "invoke_for_household", None)
        if callable(method):
            return method(name, arguments, timeout, household_id)
        return self.plugin.invoke(name, arguments, timeout)

    def invoke_with_context(
        self,
        name: str,
        arguments: dict[str, Any],
        timeout: float,
        execution_context: ProviderExecutionContext,
    ) -> Any:
        method = getattr(self.plugin, "invoke_with_context", None)
        if callable(method):
            return method(name, arguments, timeout, execution_context)
        try:
            parameters: dict[str, inspect.Parameter] = dict(
                inspect.signature(self.plugin.invoke).parameters
            )
        except (TypeError, ValueError):
            parameters = {}
        if "execution_context" in parameters:
            invoke: Any = self.plugin.invoke
            return invoke(name, arguments, timeout, execution_context=execution_context)
        return self.plugin.invoke(name, arguments, timeout)

    def invoke_with_invocation_context(
        self,
        name: str,
        arguments: dict[str, Any],
        timeout: float,
        invocation_context: InvocationContext,
    ) -> Any:
        method = getattr(self.plugin, "invoke_with_invocation_context", None)
        if callable(method):
            return method(name, arguments, timeout, invocation_context)
        try:
            parameters: dict[str, inspect.Parameter] = dict(
                inspect.signature(self.plugin.invoke).parameters
            )
        except (TypeError, ValueError):
            parameters = {}
        if "invocation_context" in parameters:
            invoke: Any = self.plugin.invoke
            return invoke(name, arguments, timeout, invocation_context=invocation_context)
        return self.plugin.invoke(name, arguments, timeout)


class McpRuntime:
    def __init__(
        self,
        kind: RuntimeKind,
        *,
        command: str | None = None,
        args: list[str] | None = None,
        url: str | None = None,
        cwd: str | None = None,
        startup_timeout: float = 15.0,
    ) -> None:
        self.kind, self.command, self.args, self.url, self.cwd, self.startup_timeout = (
            kind,
            command,
            args or [],
            url,
            cwd,
            startup_timeout,
        )
        self._running = False
        self._secret_env: dict[str, str] = {}

    def start(self, secret_env: dict[str, str]) -> None:
        if self.kind == RuntimeKind.MCP_STDIO and not self.command:
            raise PluginValidationError("stdio MCP runtime requires command")
        if self.kind == RuntimeKind.MCP_STREAMABLE_HTTP and not self.url:
            raise PluginValidationError("Streamable HTTP MCP runtime requires URL")
        self._secret_env = dict(secret_env)
        self._running = True

    def stop(self) -> None:
        self._running = False
        self._secret_env = {}

    def _params(self) -> StdioServerParameters:
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
            **self._secret_env,
        }
        return StdioServerParameters(
            command=self.command or "", args=self.args, cwd=self.cwd, env=environment
        )

    async def _list_async(self) -> list[dict[str, Any]]:
        if self.kind == RuntimeKind.MCP_STDIO:
            params = self._params()
            async with Client(params, read_timeout_seconds=self.startup_timeout) as client:
                result = await client.list_tools()
        else:
            async with Client(self.url or "", read_timeout_seconds=self.startup_timeout) as client:
                result = await client.list_tools()
        return [
            {
                "name": item.name,
                "description": item.description or "",
                "input_schema": getattr(item, "input_schema", {}),
            }
            for item in result.tools
        ]

    async def _invoke_async(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        if self.kind == RuntimeKind.MCP_STDIO:
            params = self._params()
            async with Client(params, read_timeout_seconds=timeout) as client:
                result = await client.call_tool(name, arguments, read_timeout_seconds=timeout)
        else:
            async with Client(self.url or "", read_timeout_seconds=timeout) as client:
                result = await client.call_tool(name, arguments, read_timeout_seconds=timeout)
        structured = getattr(result, "structuredContent", None)
        if structured is not None:
            return structured
        return {
            "content": [getattr(item, "text", str(item)) for item in result.content],
            "is_error": bool(getattr(result, "isError", False)),
        }

    def list_tools(self) -> list[dict[str, Any]]:
        if not self._running:
            raise RuntimeError("MCP runtime is stopped")
        return list(asyncio.run(asyncio.wait_for(self._list_async(), self.startup_timeout)))

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        if not self._running:
            raise RuntimeError("MCP runtime is stopped")
        # Each stdio call starts a fresh server process, so the bounded startup
        # allowance must also cover the transport handshake before the tool's
        # own timeout can be meaningfully enforced.
        effective_timeout = max(timeout, self.startup_timeout)
        return asyncio.run(
            asyncio.wait_for(
                self._invoke_async(name, arguments, effective_timeout), effective_timeout
            )
        )


class SecretBroker:
    def __init__(self, secrets: dict[str, str]) -> None:
        self._secrets = dict(secrets)

    def resolve(self, names: tuple[str, ...]) -> dict[str, str]:
        missing = [name for name in names if name not in self._secrets]
        if missing:
            raise PluginValidationError(f"missing declared secrets: {missing}")
        return {name: self._secrets[name] for name in names}


@dataclass(slots=True)
class RegisteredPlugin:
    manifest: PluginManifest
    runtime: PluginRuntime
    state: PluginState = PluginState.REGISTERED
    enabled: bool = False
    configuration: dict[str, Any] = field(default_factory=dict)
    tools: dict[str, ToolDescriptor] = field(default_factory=dict)
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class InvocationResult:
    outcome: InvocationOutcome
    tool_id: str
    plugin_id: str
    plugin_version: str
    elapsed_ms: float
    result: Any = None
    error_class: str | None = None
    provenance: str = ""
    external_content_trust: ExternalContentTrust = ExternalContentTrust.PLUGIN_TRUSTED
    policy_decision: PolicyDecision | None = None
    dispatch_state: DispatchState = DispatchState.ACKNOWLEDGED


class PostgresPluginStore:
    def __init__(self, database_url: str, connect_timeout: int = 5) -> None:
        self.database_url, self.connect_timeout = database_url, connect_timeout

    def save(self, plugin: RegisteredPlugin) -> None:
        with (
            psycopg.connect(self.database_url, connect_timeout=self.connect_timeout) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                """INSERT INTO anima_plugins (
                    plugin_id, plugin_version, manifest_version, requires_core, name,
                    runtime_kind, trust_class, state, enabled, configuration, manifest, last_error
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)
                ON CONFLICT (plugin_id) DO UPDATE SET
                    plugin_version=EXCLUDED.plugin_version,
                    manifest_version=EXCLUDED.manifest_version,
                    requires_core=EXCLUDED.requires_core, name=EXCLUDED.name,
                    runtime_kind=EXCLUDED.runtime_kind, trust_class=EXCLUDED.trust_class,
                    state=EXCLUDED.state, enabled=EXCLUDED.enabled,
                    configuration=EXCLUDED.configuration, manifest=EXCLUDED.manifest,
                    last_error=EXCLUDED.last_error, updated_at=now()""",
                (
                    plugin.manifest.plugin_id,
                    plugin.manifest.plugin_version,
                    plugin.manifest.manifest_version,
                    plugin.manifest.requires_core,
                    plugin.manifest.name,
                    plugin.manifest.runtime_kind.value,
                    plugin.manifest.trust_class.value,
                    plugin.state.value,
                    plugin.enabled,
                    json.dumps(plugin.configuration),
                    json.dumps(plugin.manifest.to_payload()),
                    plugin.last_error,
                ),
            )
            cursor.execute(
                "DELETE FROM anima_plugin_tools WHERE plugin_id=%s", (plugin.manifest.plugin_id,)
            )
            for tool in plugin.tools.values():
                cursor.execute(
                    "INSERT INTO anima_plugin_tools "
                    "(tool_id, plugin_id, descriptor, available) "
                    "VALUES (%s,%s,%s::jsonb,%s)",
                    (
                        tool.tool_id,
                        tool.plugin_id,
                        json.dumps(tool.to_payload()),
                        tool.availability,
                    ),
                )
            connection.commit()

    def records(self) -> list[dict[str, Any]]:
        with (
            psycopg.connect(
                self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "SELECT plugin_id, manifest, configuration, enabled "
                "FROM anima_plugins ORDER BY plugin_id"
            )
            return list(cursor.fetchall())


class PluginManager:
    def __init__(
        self,
        *,
        core_version: str = CORE_VERSION,
        journal: EventSink | None = None,
        store: PostgresPluginStore | None = None,
        secret_broker: SecretBroker | None = None,
    ) -> None:
        self.core_version, self.journal, self.store = core_version, journal, store
        self.secret_broker = secret_broker or SecretBroker({})
        self.plugins: dict[str, RegisteredPlugin] = {}
        self.tools: dict[str, ToolDescriptor] = {}

    def _compatible(self, manifest: PluginManifest) -> bool:
        return manifest.requires_core in {"*", self.core_version}

    def _audit(self, plugin: RegisteredPlugin, event_type: str, payload: dict[str, Any]) -> None:
        if not self.journal:
            return
        event = EventEnvelope.create(
            event_id=str(uuid4()),
            event_type=event_type,
            source="anima.plugins",
            subject_key=f"plugin/{plugin.manifest.plugin_id}",
            occurred_at=datetime.now(UTC),
            payload=payload,
            importance=EventImportance.IMPORTANT,
            delivery_class=DeliveryClass.GUARANTEED,
            metadata={"plugin_id": plugin.manifest.plugin_id},
        )
        self.journal.append(event)

    def register(
        self,
        manifest: PluginManifest,
        runtime: PluginRuntime,
        *,
        configuration: dict[str, Any] | None = None,
    ) -> RegisteredPlugin:
        if manifest.plugin_id in self.plugins:
            raise PluginValidationError("duplicate plugin_id")
        if not self._compatible(manifest):
            plugin = RegisteredPlugin(
                manifest, runtime, PluginState.INCOMPATIBLE, False, configuration or {}
            )
            self.plugins[manifest.plugin_id] = plugin
            if self.store:
                self.store.save(plugin)
            return plugin
        configuration = configuration or {}
        validate_instance(manifest.configuration_schema, configuration)
        descriptors = {
            ToolDescriptor.from_manifest(manifest, item).tool_id: ToolDescriptor.from_manifest(
                manifest, item
            )
            for item in manifest.tools
        }
        collisions = set(descriptors) & set(self.tools)
        if collisions:
            raise PluginValidationError(f"tool collision: {sorted(collisions)}")
        plugin = RegisteredPlugin(
            manifest, runtime, PluginState.REGISTERED, False, configuration, descriptors
        )
        self.plugins[manifest.plugin_id] = plugin
        if self.store:
            self.store.save(plugin)
        self._audit(plugin, "plugin.registered", {"version": manifest.plugin_version})
        return plugin

    def discover_native(self) -> list[PluginManifest]:
        manifests: list[PluginManifest] = []
        for entry in importlib.metadata.entry_points(group=ENTRY_POINT_GROUP):
            loaded = entry.load()
            value = loaded() if callable(loaded) else loaded
            manifest = (
                value.manifest if hasattr(value, "manifest") else PluginManifest.from_dict(value)
            )
            manifests.append(manifest)
        return manifests

    def enable(self, plugin_id: str) -> RegisteredPlugin:
        plugin = self.plugins[plugin_id]
        if plugin.state == PluginState.INCOMPATIBLE:
            return plugin
        plugin.state = PluginState.STARTING
        attempts = min(max(int(plugin.manifest.restart_policy.get("max_attempts", 1)), 1), 3)
        for attempt in range(attempts):
            try:
                env = self.secret_broker.resolve(plugin.manifest.required_secrets)
                plugin.runtime.start(env)
                discovered = plugin.runtime.list_tools()
                new_tools: dict[str, ToolDescriptor] = {}
                for item in discovered:
                    name = str(item["name"])
                    declared = next(
                        (x for x in plugin.manifest.tools if str(x["name"]) == name), None
                    )
                    if declared is None:
                        raise PluginValidationError(f"undeclared tool: {name}")
                    validate_json_schema(
                        dict(
                            item.get(
                                "input_schema", declared.get("input_schema", {"type": "object"})
                            )
                        )
                    )
                    descriptor = ToolDescriptor.from_manifest(
                        plugin.manifest, {**declared, "name": name}, available=True
                    )
                    validate_json_schema(descriptor.input_schema)
                    if descriptor.output_schema:
                        validate_json_schema(descriptor.output_schema)
                    new_tools[descriptor.tool_id] = descriptor
                self.tools.update(new_tools)
                plugin.tools = new_tools
                plugin.enabled, plugin.state, plugin.last_error = True, PluginState.HEALTHY, None
                if self.store:
                    self.store.save(plugin)
                self._audit(
                    plugin, "plugin.healthy", {"tools": sorted(new_tools), "attempt": attempt + 1}
                )
                break
            except Exception as exc:
                plugin.state, plugin.enabled, plugin.last_error = (
                    PluginState.FAILED,
                    False,
                    str(exc),
                )
                plugin.tools.clear()
                try:
                    plugin.runtime.stop()
                except Exception:
                    pass
                if attempt + 1 < attempts:
                    time.sleep(
                        min(
                            float(plugin.manifest.restart_policy.get("backoff_seconds", 0.01)), 0.25
                        )
                    )
                    plugin.state = PluginState.STARTING
                    continue
                if self.store:
                    self.store.save(plugin)
                self._audit(
                    plugin,
                    "plugin.failed",
                    {"error_class": type(exc).__name__, "attempts": attempts},
                )
        return plugin

    def disable(self, plugin_id: str) -> RegisteredPlugin:
        plugin = self.plugins[plugin_id]
        plugin.state = PluginState.STOPPING
        for tool_id in list(plugin.tools):
            self.tools.pop(tool_id, None)
        try:
            plugin.runtime.stop()
        finally:
            plugin.tools.clear()
            plugin.enabled = False
            plugin.state = PluginState.DISABLED
            if self.store:
                self.store.save(plugin)
            self._audit(plugin, "plugin.disabled", {})
        return plugin

    def list_plugins(self, *, enabled_only: bool = False) -> list[RegisteredPlugin]:
        values = list(self.plugins.values())
        return [x for x in values if x.enabled] if enabled_only else values

    def list_tools(
        self, *, plugin_id: str | None = None, capability_id: str | None = None
    ) -> list[ToolDescriptor]:
        return sorted(
            [
                x
                for x in self.tools.values()
                if (plugin_id is None or x.plugin_id == plugin_id)
                and (capability_id is None or x.capability_id == capability_id)
            ],
            key=lambda x: x.tool_id,
        )

    def list_capabilities(self) -> list[str]:
        return sorted(
            {
                capability
                for plugin in self.plugins.values()
                for capability in plugin.manifest.capabilities
            }
        )

    def restore(self, runtimes: dict[str, PluginRuntime]) -> list[RegisteredPlugin]:
        """Restore persisted manifests/configuration; only supplied runtimes may start."""
        if not self.store:
            return []
        restored: list[RegisteredPlugin] = []
        for row in self.store.records():
            plugin_id = str(row["plugin_id"])
            runtime = runtimes.get(plugin_id)
            if runtime is None:
                continue
            plugin = self.register(
                PluginManifest.from_dict(dict(row["manifest"])),
                runtime,
                configuration=dict(row["configuration"]),
            )
            restored.append(plugin)
            if bool(row["enabled"]):
                self.enable(plugin_id)
        return restored

    def emit_event(
        self, plugin_id: str, event_type: str, subject_key: str, payload: dict[str, Any]
    ) -> str:
        plugin = self.plugins[plugin_id]
        if event_type not in plugin.manifest.events:
            raise PluginValidationError("event type was not declared")
        event = EventEnvelope.create(
            event_id=str(uuid4()),
            event_type=event_type,
            source=f"plugin:{plugin_id}",
            subject_key=subject_key,
            occurred_at=datetime.now(UTC),
            payload=payload,
            metadata={"plugin_id": plugin_id, "plugin_version": plugin.manifest.plugin_version},
        )
        if not self.journal:
            raise PluginValidationError("event ingress requires journal")
        self.journal.append(event)
        return event.event_id

    def invoke(
        self,
        tool_id: str,
        arguments: dict[str, Any],
        *,
        household_id: UUID,
        action_intent_id: UUID | None = None,
        identity: IdentityContext,
        origin: RequestOrigin = RequestOrigin.DIRECT_USER,
        resource_id: UUID | None = None,
        capability_id: UUID | None = None,
        policy_service: PolicyService | None = None,
        policy_context: PolicyContext | None = None,
        confirmation: Any | None = None,
        execution_context: ProviderExecutionContext | None = None,
        invocation_context: InvocationContext | None = None,
    ) -> InvocationResult:
        started = time.monotonic()
        tool = self.tools.get(tool_id)
        if tool is None:
            return InvocationResult(
                InvocationOutcome.PLUGIN_UNAVAILABLE, tool_id, "", "", 0, error_class="UnknownTool"
            )
        plugin = self.plugins[tool.plugin_id]
        if invocation_context is not None and invocation_context.household_id != household_id:
            return InvocationResult(
                InvocationOutcome.POLICY_DENIED,
                tool_id,
                tool.plugin_id,
                tool.version,
                0,
                error_class="INVOCATION_CONTEXT_HOUSEHOLD_MISMATCH",
                provenance=tool.provenance,
                external_content_trust=tool.external_content_trust,
            )
        try:
            validate_instance(tool.input_schema, arguments)
        except PluginValidationError as exc:
            return InvocationResult(
                InvocationOutcome.INVALID_ARGUMENTS,
                tool_id,
                tool.plugin_id,
                tool.version,
                (time.monotonic() - started) * 1000,
                error_class=type(exc).__name__,
                provenance=tool.provenance,
                external_content_trust=tool.external_content_trust,
            )
        if policy_service is None:
            return InvocationResult(
                InvocationOutcome.POLICY_DENIED,
                tool_id,
                tool.plugin_id,
                tool.version,
                (time.monotonic() - started) * 1000,
                error_class="POLICY_REQUIRED",
                provenance=tool.provenance,
                external_content_trust=tool.external_content_trust,
            )
        decision: PolicyDecision | None = None
        if policy_service:
            semantic_action = tool.semantic_action
            if resource_id is None and arguments.get("resource_id") is not None:
                try:
                    resource_id = UUID(str(arguments["resource_id"]))
                except ValueError:
                    return InvocationResult(
                        InvocationOutcome.INVALID_ARGUMENTS,
                        tool_id,
                        tool.plugin_id,
                        tool.version,
                        (time.monotonic() - started) * 1000,
                        error_class="InvalidResourceId",
                        provenance=tool.provenance,
                        external_content_trust=tool.external_content_trust,
                    )
            if capability_id is None and arguments.get("capability_id") is not None:
                try:
                    capability_id = UUID(str(arguments["capability_id"]))
                except ValueError:
                    return InvocationResult(
                        InvocationOutcome.INVALID_ARGUMENTS,
                        tool_id,
                        tool.plugin_id,
                        tool.version,
                        (time.monotonic() - started) * 1000,
                        error_class="InvalidCapabilityId",
                        provenance=tool.provenance,
                        external_content_trust=tool.external_content_trust,
                    )
            intent_kwargs: dict[str, Any] = {
                "household_id": household_id,
                "semantic_action": semantic_action,
                "resource_id": resource_id,
                "capability_id": capability_id,
                "principal_id": identity.principal_id,
                "origin": origin,
                "graph_metadata": {
                    "plugin_id": tool.plugin_id,
                    "security_sensitive": tool.risk_class.startswith("SECURITY"),
                    "read_only": tool.read_only,
                    "writable": not tool.read_only,
                    "external_side_effect": tool.risk_class == "EXTERNAL_SIDE_EFFECT",
                    "financial": tool.risk_class == "FINANCIAL_PURCHASE",
                },
            }
            if policy_context is not None:
                intent_kwargs["truth"] = policy_context.truth
            intent = ActionIntent.create(
                action_intent_id=action_intent_id or uuid4(),
                **intent_kwargs,
            )
            if intent.risk_class.value != tool.risk_class:
                return InvocationResult(
                    InvocationOutcome.POLICY_DENIED,
                    tool_id,
                    tool.plugin_id,
                    tool.version,
                    (time.monotonic() - started) * 1000,
                    error_class="TOOL_RISK_CLASS_MISMATCH",
                    provenance=tool.provenance,
                    external_content_trust=tool.external_content_trust,
                )
            decision = policy_service.evaluate(intent, identity, policy_context, confirmation)
            outcome = {
                Decision.DENY: InvocationOutcome.POLICY_DENIED,
                Decision.REQUIRE_CONFIRMATION: InvocationOutcome.REQUIRE_CONFIRMATION,
                Decision.REQUIRE_STRONGER_AUTH: InvocationOutcome.REQUIRE_STRONGER_AUTH,
            }.get(decision.decision)
            if outcome:
                return InvocationResult(
                    outcome,
                    tool_id,
                    tool.plugin_id,
                    tool.version,
                    (time.monotonic() - started) * 1000,
                    error_class=decision.reason_code,
                    provenance=tool.provenance,
                    external_content_trust=tool.external_content_trust,
                    policy_decision=decision,
                )
        try:
            household_invoke = getattr(plugin.runtime, "invoke_for_household", None)
            contextual_invoke = getattr(plugin.runtime, "invoke_with_context", None)
            invocation_contextual_invoke = getattr(
                plugin.runtime, "invoke_with_invocation_context", None
            )
            if invocation_context is not None and callable(invocation_contextual_invoke):
                result = invocation_contextual_invoke(
                    tool.name, arguments, tool.timeout, invocation_context
                )
            elif execution_context is not None and callable(contextual_invoke):
                result = contextual_invoke(tool.name, arguments, tool.timeout, execution_context)
            elif callable(household_invoke):
                result = household_invoke(tool.name, arguments, tool.timeout, household_id)
            else:
                result = plugin.runtime.invoke(tool.name, arguments, tool.timeout)
            if isinstance(result, dict) and result.get("is_error") is True:
                raise RuntimeError("plugin reported a tool error")
            if tool.output_schema and not isinstance(result, dict):
                raise PluginValidationError("result is not a JSON object")
            if tool.output_schema:
                validate_instance(tool.output_schema, result)
            result_outcome = result.get("outcome") if isinstance(result, dict) else None
            if result_outcome in {"VERIFICATION_FAILED", "SERVICE_FAILED", "TARGET_UNAVAILABLE"}:
                return InvocationResult(
                    InvocationOutcome.VERIFICATION_FAILED,
                    tool_id,
                    tool.plugin_id,
                    tool.version,
                    (time.monotonic() - started) * 1000,
                    result=result,
                    error_class=str(result_outcome),
                    provenance=tool.provenance,
                    external_content_trust=tool.external_content_trust,
                    policy_decision=decision,
                    dispatch_state=DispatchState.POSSIBLY_DISPATCHED,
                )
            if result_outcome == "UNKNOWN_RESULT":
                return InvocationResult(
                    InvocationOutcome.UNKNOWN_RESULT,
                    tool_id,
                    tool.plugin_id,
                    tool.version,
                    (time.monotonic() - started) * 1000,
                    result=result,
                    error_class="UNKNOWN_RESULT",
                    provenance=tool.provenance,
                    external_content_trust=tool.external_content_trust,
                    policy_decision=decision,
                    dispatch_state=DispatchState.POSSIBLY_DISPATCHED,
                )
            return InvocationResult(
                InvocationOutcome.SUCCESS,
                tool_id,
                tool.plugin_id,
                tool.version,
                (time.monotonic() - started) * 1000,
                result=result,
                provenance=tool.provenance,
                external_content_trust=tool.external_content_trust,
                policy_decision=decision,
                dispatch_state=DispatchState.ACKNOWLEDGED,
            )
        except TimeoutError:
            return InvocationResult(
                InvocationOutcome.PLUGIN_TIMEOUT,
                tool_id,
                tool.plugin_id,
                tool.version,
                (time.monotonic() - started) * 1000,
                error_class="TimeoutError",
                provenance=tool.provenance,
                external_content_trust=tool.external_content_trust,
                policy_decision=decision,
                dispatch_state=DispatchState.POSSIBLY_DISPATCHED,
            )
        except PluginValidationError as exc:
            return InvocationResult(
                InvocationOutcome.INVALID_RESULT,
                tool_id,
                tool.plugin_id,
                tool.version,
                (time.monotonic() - started) * 1000,
                error_class=type(exc).__name__,
                provenance=tool.provenance,
                external_content_trust=tool.external_content_trust,
                policy_decision=decision,
                dispatch_state=DispatchState.BEFORE_DISPATCH,
            )
        except Exception as exc:
            return InvocationResult(
                InvocationOutcome.PLUGIN_ERROR,
                tool_id,
                tool.plugin_id,
                tool.version,
                (time.monotonic() - started) * 1000,
                error_class=type(exc).__name__,
                provenance=tool.provenance,
                external_content_trust=tool.external_content_trust,
                policy_decision=decision,
                dispatch_state=DispatchState.POSSIBLY_DISPATCHED,
            )


class NativeSimulatorPlugin:
    def __init__(self) -> None:
        self.secret_env: dict[str, str] = {}

    def start(self, secret_env: dict[str, str]) -> None:
        self.secret_env = dict(secret_env)

    def stop(self) -> None:
        self.secret_env = {}

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "synthetic_status",
                "description": "Read synthetic status",
                "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
                "output_schema": {
                    "type": "object",
                    "required": ["status"],
                    "properties": {"status": {"type": "string"}},
                    "additionalProperties": False,
                },
            }
        ]

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        if name != "synthetic_status":
            raise PluginValidationError("unknown native tool")
        return {"status": "synthetic-ready"}


NATIVE_SIMULATOR_MANIFEST = PluginManifest(
    plugin_id="anima.reference.native-simulator",
    plugin_version="0.1.0",
    manifest_version=MANIFEST_VERSION,
    requires_core=CORE_VERSION,
    name="Native simulator reference",
    description="Safe synthetic read-only capability for Phase 5 validation",
    runtime_kind=RuntimeKind.TRUSTED_NATIVE,
    trust_class=TrustClass.TRUSTED_NATIVE,
    capabilities=("home.simulation",),
    tools=(
        {
            "name": "synthetic_status",
            "description": "Read synthetic status",
            "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
            "output_schema": {
                "type": "object",
                "required": ["status"],
                "properties": {"status": {"type": "string"}},
                "additionalProperties": False,
            },
            "semantic_action": "query_plugin",
            "risk_class": "READ_ONLY",
            "read_only": True,
            "idempotency": "IDEMPOTENT",
            "external_content_trust": "LOCAL_TRUSTED",
        },
    ),
    source="builtin:anima_ha.plugins",
)


class ReferenceNativePlugin(NativeSimulatorPlugin):
    manifest = NATIVE_SIMULATOR_MANIFEST


def native_reference_factory() -> ReferenceNativePlugin:
    return ReferenceNativePlugin()
