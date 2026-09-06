"""ANIMA-owned declarative scenes backed by canonical resources.

Scenes contain only bounded semantic power intents.  Applying a scene is
performed by the Core command gateway as a sequence of ordinary verified
controls; this module never accepts Home Assistant entity IDs, services, or
arbitrary automation payloads.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from anima_ha.plugins import (
    CORE_VERSION,
    MANIFEST_VERSION,
    ExternalContentTrust,
    Idempotency,
    InvocationContext,
    PluginManifest,
    PluginValidationError,
    RuntimeKind,
    TrustClass,
)

SCENE_SCHEMA_VERSION = 1
MAX_SCENE_NAME = 80
MAX_SCENE_STEPS = 16


class SceneError(RuntimeError):
    """Base class for scene validation and persistence failures."""


class SceneNotFound(SceneError):
    """A requested scene is not in the caller's household."""


class SceneConflict(SceneError):
    """A scene write used stale or conflicting canonical state."""


@dataclass(frozen=True, slots=True)
class SceneStep:
    resource_id: UUID
    desired_on: bool

    def to_payload(self) -> dict[str, Any]:
        return {"resource_id": str(self.resource_id), "desired_on": self.desired_on}


def _steps(value: Any) -> tuple[SceneStep, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_SCENE_STEPS:
        raise SceneError(f"steps must contain 1 to {MAX_SCENE_STEPS} items")
    result: list[SceneStep] = []
    seen: set[UUID] = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {"resource_id", "desired_on"}:
            raise SceneError("scene steps contain only resource_id and desired_on")
        try:
            resource_id = UUID(str(item["resource_id"]))
        except (TypeError, ValueError) as exc:
            raise SceneError("scene resource_id must be a UUID") from exc
        if resource_id in seen:
            raise SceneError("scene cannot contain duplicate resources")
        if not isinstance(item["desired_on"], bool):
            raise SceneError("scene desired_on must be boolean")
        seen.add(resource_id)
        result.append(SceneStep(resource_id, item["desired_on"]))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class Scene:
    scene_id: UUID
    household_id: UUID
    name: str
    steps: tuple[SceneStep, ...]
    enabled: bool
    creator_principal_id: UUID | None
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        household_id: UUID,
        name: str,
        steps: Any,
        creator_principal_id: UUID | None,
        now: datetime | None = None,
        scene_id: UUID | None = None,
    ) -> Scene:
        clean_name = str(name).strip()
        if not 1 <= len(clean_name) <= MAX_SCENE_NAME:
            raise SceneError(f"name must contain 1 to {MAX_SCENE_NAME} characters")
        at = (now or datetime.now(UTC)).astimezone(UTC)
        return cls(
            scene_id=scene_id or uuid4(),
            household_id=household_id,
            name=clean_name,
            steps=_steps(steps),
            enabled=True,
            creator_principal_id=creator_principal_id,
            version=1,
            created_at=at,
            updated_at=at,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "scene_id": str(self.scene_id),
            "name": self.name,
            "steps": [step.to_payload() for step in self.steps],
            "enabled": self.enabled,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


def _from_row(row: dict[str, Any]) -> Scene:
    return Scene(
        scene_id=row["scene_id"],
        household_id=row["household_id"],
        name=row["name"],
        steps=_steps(row["steps"] if isinstance(row["steps"], list) else json.loads(row["steps"])),
        enabled=bool(row["enabled"]),
        creator_principal_id=row["creator_principal_id"],
        version=int(row["version"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostgresSceneStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def list(self, household_id: UUID) -> list[Scene]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM anima_scenes WHERE household_id=%s ORDER BY name, scene_id",
                (household_id,),
            )
            return [_from_row(dict(row)) for row in cursor.fetchall()]

    def get(self, household_id: UUID, scene_id: UUID) -> Scene:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM anima_scenes WHERE household_id=%s AND scene_id=%s",
                (household_id, scene_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise SceneNotFound(str(scene_id))
        return _from_row(dict(row))

    def create(self, scene: Scene) -> Scene:
        with self._connect() as connection, connection.cursor() as cursor:
            try:
                cursor.execute(
                    """INSERT INTO anima_scenes
                    (scene_id, household_id, name, steps, enabled, creator_principal_id,
                     version, created_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                    (
                        scene.scene_id,
                        scene.household_id,
                        scene.name,
                        json.dumps([step.to_payload() for step in scene.steps]),
                        scene.enabled,
                        scene.creator_principal_id,
                        scene.version,
                        scene.created_at,
                        scene.updated_at,
                    ),
                )
            except psycopg.errors.UniqueViolation as exc:
                raise SceneConflict("scene identity already exists") from exc
            row = cursor.fetchone()
            connection.commit()
        assert row is not None
        return _from_row(dict(row))

    def update(
        self,
        household_id: UUID,
        scene_id: UUID,
        expected_version: int,
        *,
        name: str,
        steps: Any,
        enabled: bool,
        now: datetime,
    ) -> Scene:
        clean_name = str(name).strip()
        if not 1 <= len(clean_name) <= MAX_SCENE_NAME:
            raise SceneError(f"name must contain 1 to {MAX_SCENE_NAME} characters")
        normalized_steps = _steps(steps)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE anima_scenes SET name=%s, steps=%s, enabled=%s,
                   version=version+1, updated_at=%s
                   WHERE household_id=%s AND scene_id=%s AND version=%s
                   RETURNING *""",
                (
                    clean_name,
                    json.dumps([step.to_payload() for step in normalized_steps]),
                    enabled,
                    now.astimezone(UTC),
                    household_id,
                    scene_id,
                    expected_version,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                connection.rollback()
                current = self.get(household_id, scene_id)
                raise SceneConflict(f"scene version is stale; current version is {current.version}")
            connection.commit()
        return _from_row(dict(row))


class InMemorySceneStore:
    def __init__(self) -> None:
        self.scenes: dict[UUID, Scene] = {}

    def list(self, household_id: UUID) -> list[Scene]:
        return sorted(
            (scene for scene in self.scenes.values() if scene.household_id == household_id),
            key=lambda scene: (scene.name, scene.scene_id),
        )

    def get(self, household_id: UUID, scene_id: UUID) -> Scene:
        scene = self.scenes.get(scene_id)
        if scene is None or scene.household_id != household_id:
            raise SceneNotFound(str(scene_id))
        return scene

    def create(self, scene: Scene) -> Scene:
        if scene.scene_id in self.scenes:
            raise SceneConflict("scene identity already exists")
        self.scenes[scene.scene_id] = scene
        return scene

    def update(
        self,
        household_id: UUID,
        scene_id: UUID,
        expected_version: int,
        *,
        name: str,
        steps: Any,
        enabled: bool,
        now: datetime,
    ) -> Scene:
        current = self.get(household_id, scene_id)
        if current.version != expected_version:
            raise SceneConflict("scene version is stale")
        updated = replace(
            current,
            name=str(name).strip(),
            steps=_steps(steps),
            enabled=enabled,
            version=current.version + 1,
            updated_at=now.astimezone(UTC),
        )
        self.scenes[scene_id] = updated
        return updated


def _tool(
    name: str, description: str, schema: dict[str, Any], *, read_only: bool
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "input_schema": schema,
        "output_schema": {"type": "object"},
        "risk_class": "READ_ONLY" if read_only else "LOW_RISK_HOME_CONTROL",
        "semantic_action": f"scenes.{name}",
        "read_only": read_only,
        "idempotency": Idempotency.IDEMPOTENT.value if read_only else Idempotency.KEYED.value,
        "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
    }


SCENE_STEP_SCHEMA = {
    "type": "object",
    "properties": {
        "resource_id": {"type": "string", "format": "uuid"},
        "desired_on": {"type": "boolean"},
    },
    "required": ["resource_id", "desired_on"],
    "additionalProperties": False,
}
SCENE_SCHEMA = {
    "type": "object",
    "properties": {
        "scene_id": {"type": "string", "format": "uuid"},
        "expected_version": {"type": "integer", "minimum": 1},
        "name": {"type": "string", "minLength": 1, "maxLength": MAX_SCENE_NAME},
        "steps": {
            "type": "array",
            "items": SCENE_STEP_SCHEMA,
            "minItems": 1,
            "maxItems": MAX_SCENE_STEPS,
        },
        "enabled": {"type": "boolean"},
    },
    "additionalProperties": False,
}

SCENES_MANIFEST = PluginManifest(
    plugin_id="anima.scenes",
    plugin_version="0.1.0",
    manifest_version=MANIFEST_VERSION,
    requires_core=CORE_VERSION,
    name="ANIMA scenes",
    description="Bounded declarative presets of canonical household power states",
    runtime_kind=RuntimeKind.TRUSTED_NATIVE,
    trust_class=TrustClass.TRUSTED_NATIVE,
    capabilities=("scenes",),
    tools=(
        _tool(
            "list_scenes",
            "List household scene presets",
            {"type": "object", "additionalProperties": False},
            read_only=True,
        ),
        _tool(
            "create_scene",
            "Create a declarative household scene",
            {
                "type": "object",
                "properties": {
                    "name": SCENE_SCHEMA["properties"]["name"],
                    "steps": SCENE_SCHEMA["properties"]["steps"],
                },
                "required": ["name", "steps"],
                "additionalProperties": False,
            },
            read_only=False,
        ),
        _tool(
            "update_scene",
            "Update a scene with optimistic version protection",
            SCENE_SCHEMA,
            read_only=False,
        ),
    ),
    source="builtin:anima_ha.scenes",
)


class SceneNativePlugin:
    def __init__(self, store: Any, resource_validator: Callable[[UUID, UUID], bool]) -> None:
        self.store = store
        self.resource_validator = resource_validator

    def start(self, secret_env: dict[str, str]) -> None:
        if secret_env:
            raise PluginValidationError("scenes accept no secrets")

    def stop(self) -> None:
        return None

    def list_tools(self) -> list[dict[str, Any]]:
        return [dict(item) for item in SCENES_MANIFEST.tools]

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        del name, arguments, timeout
        raise PluginValidationError("scenes require trusted invocation context")

    def invoke_with_invocation_context(
        self, name: str, arguments: dict[str, Any], timeout: float, context: InvocationContext
    ) -> Any:
        del timeout
        if name == "list_scenes":
            return {
                "scenes": [scene.to_payload() for scene in self.store.list(context.household_id)]
            }
        if name == "create_scene":
            scene = Scene.create(
                household_id=context.household_id,
                name=str(arguments["name"]),
                steps=arguments["steps"],
                creator_principal_id=context.principal_id,
            )
            self._validate_resources(context.household_id, scene.steps)
            return {"scene": self.store.create(scene).to_payload()}
        if name != "update_scene":
            raise SceneError(f"unknown scene operation: {name}")
        scene = self.store.get(context.household_id, UUID(str(arguments["scene_id"])))
        steps = arguments.get("steps", [step.to_payload() for step in scene.steps])
        name_value = arguments.get("name", scene.name)
        enabled = bool(arguments.get("enabled", scene.enabled))
        normalized = _steps(steps)
        self._validate_resources(context.household_id, normalized)
        updated = self.store.update(
            context.household_id,
            scene.scene_id,
            int(arguments["expected_version"]),
            name=str(name_value),
            steps=[step.to_payload() for step in normalized],
            enabled=enabled,
            now=datetime.now(UTC),
        )
        return {"scene": updated.to_payload()}

    def _validate_resources(self, household_id: UUID, steps: tuple[SceneStep, ...]) -> None:
        if not all(self.resource_validator(household_id, step.resource_id) for step in steps):
            raise SceneError("every scene resource must be a commissioned household power resource")


def scene_items(store: Any, household_id: UUID) -> list[dict[str, Any]]:
    return [scene.to_payload() for scene in store.list(household_id)]
