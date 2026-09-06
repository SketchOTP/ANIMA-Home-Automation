from __future__ import annotations

from uuid import uuid4

import pytest

from anima_ha.plugins import InvocationContext
from anima_ha.policy import RequestOrigin
from anima_ha.scenes import InMemorySceneStore, SceneConflict, SceneError, SceneNativePlugin


def _context(household_id):
    return InvocationContext(
        household_id=household_id,
        principal_id=uuid4(),
        episode_id=None,
        tool_request_id=uuid4(),
        ordinal=1,
        system_idempotency_key="scene-test",
        origin=RequestOrigin.DIRECT_USER,
    )


def test_scene_plugin_is_household_scoped_and_versioned() -> None:
    household_id = uuid4()
    resource_id = uuid4()
    store = InMemorySceneStore()
    plugin = SceneNativePlugin(
        store,
        lambda household, resource: household == household_id and resource == resource_id,
    )
    context = _context(household_id)
    created = plugin.invoke_with_invocation_context(
        "create_scene",
        {"name": "Night", "steps": [{"resource_id": str(resource_id), "desired_on": False}]},
        1.0,
        context,
    )
    scene = created["scene"]
    assert scene["version"] == 1
    assert plugin.invoke_with_invocation_context("list_scenes", {}, 1.0, context)["scenes"] == [
        scene
    ]

    updated = plugin.invoke_with_invocation_context(
        "update_scene",
        {
            "scene_id": scene["scene_id"],
            "expected_version": 1,
            "name": "Sleep",
            "steps": scene["steps"],
            "enabled": False,
        },
        1.0,
        context,
    )
    assert updated["scene"]["name"] == "Sleep"
    assert updated["scene"]["version"] == 2
    with pytest.raises(SceneConflict):
        plugin.invoke_with_invocation_context(
            "update_scene",
            {**updated["scene"], "expected_version": 1},
            1.0,
            context,
        )


def test_scene_rejects_uncommissioned_or_duplicate_resources() -> None:
    household_id = uuid4()
    resource_id = uuid4()
    plugin = SceneNativePlugin(InMemorySceneStore(), lambda household, resource: False)
    with pytest.raises(SceneError):
        plugin.invoke_with_invocation_context(
            "create_scene",
            {
                "name": "Unsafe",
                "steps": [
                    {"resource_id": str(resource_id), "desired_on": True},
                    {"resource_id": str(resource_id), "desired_on": False},
                ],
            },
            1.0,
            _context(household_id),
        )
