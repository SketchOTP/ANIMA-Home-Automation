from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from anima_ha.graph import PostgresHouseholdGraph
from anima_ha.plugins import NativeRuntime, PluginManager
from anima_ha.policy import Assurance, EvidenceType, IdentityEvidence, PolicyService
from anima_ha.ui_api import UIIdentity
from anima_ha.ui_runtime import CoreUICommandGateway
from anima_ha.users import HOUSEHOLD_USERS_MANIFEST, HouseholdUsersNativePlugin

HOUSEHOLD = UUID("00000000-0000-0000-0000-000000000101")
PERSON = UUID("00000000-0000-0000-0000-000000000102")


class AllowEvaluator:
    def evaluate(self, document: dict[str, object]) -> dict[str, object]:
        del document
        return {"decision": "ALLOW", "reason_code": "TEST_ALLOW", "policy_version": "test"}


class Graph:
    def __init__(self) -> None:
        self.person = SimpleNamespace(
            canonical_id=PERSON,
            name="Tym",
            metadata={
                "semantic_role": "owner",
                "sentry_access": "LIMITED",
                "wifi_macs": [],
                "sentry_onboarding_state": "PENDING_CAMERA_PROFILE",
            },
        )

    def members_of_household(self, household_id: UUID) -> list[Any]:
        assert household_id == HOUSEHOLD
        return [self.person]

    def update_person_profile(self, household_id: UUID, person_id: UUID, **changes: Any) -> Any:
        assert household_id == HOUSEHOLD and person_id == PERSON
        self.person.metadata = PostgresHouseholdGraph._person_metadata(
            self.person.metadata, **changes
        )
        if changes.get("name") is not None:
            self.person.name = changes["name"]
        return self.person


class FaceClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def start(self, person_id: str, display_name: str) -> dict[str, Any]:
        self.calls.append("start")
        return {
            "session_id": "session",
            "person_id": person_id,
            "display_name": display_name,
            "accepted_samples": 0,
            "target_samples": 8,
            "ready_to_save": False,
            "accepted_poses": {},
            "samples": [],
        }

    def capture(self, person_id: str, session_id: str, pose: str) -> dict[str, Any]:
        self.calls.append("capture")
        return {
            "session_id": session_id,
            "person_id": person_id,
            "display_name": "Tym",
            "accepted_samples": 1,
            "target_samples": 8,
            "ready_to_save": False,
            "accepted_poses": {pose: 1},
            "samples": [
                {
                    "sample_id": "sample",
                    "pose": pose,
                    "quality": {"sharpness": 100},
                    "preview_jpeg_base64": "AQID",
                }
            ],
        }

    def remove_sample(self, person_id: str, session_id: str, sample_id: str) -> dict[str, Any]:
        del sample_id
        self.calls.append("remove_sample")
        return {
            "session_id": session_id,
            "person_id": person_id,
            "display_name": "Tym",
            "accepted_samples": 0,
            "target_samples": 8,
            "ready_to_save": False,
            "accepted_poses": {},
            "samples": [],
        }

    def commit(self, person_id: str, session_id: str) -> dict[str, Any]:
        del session_id
        self.calls.append("commit")
        return {"ok": True, "person_id": person_id, "accepted_samples": 8}

    def cancel(self, person_id: str, session_id: str) -> dict[str, Any]:
        del person_id, session_id
        self.calls.append("cancel")
        return {"ok": True, "cancelled": True}

    def delete(self, person_id: str) -> dict[str, Any]:
        self.calls.append("delete")
        return {"ok": True, "deleted_person_id": person_id}


def identity() -> UIIdentity:
    now = datetime.now(UTC)
    evidence = IdentityEvidence(
        uuid4(),
        HOUSEHOLD,
        PERSON,
        EvidenceType.AUTHENTICATED_SESSION,
        "test",
        now,
        now,
        now + timedelta(hours=1),
        Assurance.AUTHENTICATED,
        90,
        "test",
    )
    return UIIdentity(HOUSEHOLD, PERSON, "ha-user", evidence)


def gateway(graph: Graph, client: FaceClient) -> CoreUICommandGateway:
    manager = PluginManager()
    manager.register(
        HOUSEHOLD_USERS_MANIFEST,
        NativeRuntime(HouseholdUsersNativePlugin(graph)),  # type: ignore[arg-type]
    )
    manager.enable(HOUSEHOLD_USERS_MANIFEST.plugin_id)
    return CoreUICommandGateway(
        manager,
        PolicyService(AllowEvaluator()),
        household_graph=graph,  # type: ignore[arg-type]
        sentry_identity_profiles=client,  # type: ignore[arg-type]
        policy_role_resolver=lambda _: "owner",
    )


def test_metadata_updates_replace_old_access_and_wifi_values() -> None:
    existing = {
        "semantic_role": "member",
        "sentry_access": "LIMITED",
        "wifi_macs": ["00:00:00:00:00:01"],
        "sentry_onboarding_state": "PENDING_CAMERA_PROFILE",
    }
    updated = PostgresHouseholdGraph._person_metadata(
        existing,
        semantic_role="owner",
        access_level="UNRESTRICTED",
        wifi_macs=["AA-BB-CC-DD-EE-FF"],
    )
    assert updated["semantic_role"] == "owner"
    assert updated["sentry_access"] == "UNRESTRICTED"
    assert updated["wifi_macs"] == ["aa:bb:cc:dd:ee:ff"]


def test_face_profile_workflow_is_authorized_and_persists_profile_projection() -> None:
    graph = Graph()
    client = FaceClient()
    commands = gateway(graph, client)

    started = commands.user_mutation(identity(), "face-start", {"person_id": str(PERSON)})
    captured = commands.user_mutation(
        identity(),
        "face-capture",
        {"person_id": str(PERSON), "session_id": "session", "pose": "straight"},
    )
    committed = commands.user_mutation(
        identity(), "face-commit", {"person_id": str(PERSON), "session_id": "session"}
    )

    assert started["status"] == "SUCCEEDED"
    assert captured["result"]["samples"][0]["preview_jpeg_base64"] == "AQID"
    assert committed["status"] == "SUCCEEDED"
    assert graph.person.metadata["sentry_profile_id"] == str(PERSON)
    assert graph.person.metadata["sentry_profile_sample_count"] == 8
    assert graph.person.metadata["sentry_onboarding_state"] == "ACTIVE"

    deleted = commands.user_mutation(identity(), "face-delete", {"person_id": str(PERSON)})
    assert deleted["status"] == "SUCCEEDED"
    assert "sentry_profile_id" not in graph.person.metadata
    assert "sentry_profile_sample_count" not in graph.person.metadata
    assert graph.person.metadata["sentry_onboarding_state"] == "REVOKED"
    assert client.calls == ["start", "capture", "commit", "delete"]
