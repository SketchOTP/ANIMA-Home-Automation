from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from anima_ha.graph import CanonicalNode, CommissioningDocument, NodeKind
from anima_ha.ha_connection_setup import (
    HAConnectionStore,
    HASetupError,
    VerifiedHAOwner,
    commission_owner,
)
from anima_ha.ui_api import HomeAssistantOAuth, UIAuthError, UIConfig, UIService, create_app

INSTANCE = UUID("00000000-0000-0000-0000-000000000801")
SECRET = "synthetic-private-connection-credential-should-never-appear"


def test_deployment_version_is_explicit_and_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    from anima_ha.ui_runtime import owner_ha_version

    monkeypatch.delenv("ANIMA_HA_EXPECTED_VERSION", raising=False)
    assert owner_ha_version() == "2026.8.2"
    monkeypatch.setenv("ANIMA_HA_EXPECTED_VERSION", "2026.9.0")
    assert owner_ha_version() == "2026.9.0"
    monkeypatch.setenv("ANIMA_HA_EXPECTED_VERSION", "anything")
    with pytest.raises(ValueError, match="not a qualified target"):
        owner_ha_version()


def connection() -> dict[str, Any]:
    return {
        "version": 1,
        "token": SECRET,
        "user_id": "verified-owner",
        "household_id": str(INSTANCE),
        "instance_id": str(INSTANCE),
        "base_url": "http://configured-ha:8123",
    }


def test_connection_file_is_private_restart_safe_and_never_replaced(tmp_path: Path) -> None:
    path = tmp_path / "private" / "ha.json"
    store = HAConnectionStore(path)
    store.save_new(connection())
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert HAConnectionStore(path).read() == connection()
    before = path.read_bytes()
    store.save_new({**connection(), "token": "do-not-replace-existing-credential"})
    assert path.read_bytes() == before
    with pytest.raises(HASetupError, match="ALREADY_COMMISSIONED"):
        store.save_new({**connection(), "user_id": "different-owner"})
    assert path.read_bytes() == before


def test_connection_file_rejects_symlink_and_permissive_storage(tmp_path: Path) -> None:
    target = tmp_path / "ha.json"
    target.write_text(json.dumps(connection()))
    with pytest.raises(HASetupError, match="FILE_UNSAFE"):
        HAConnectionStore(target).read()
    target.chmod(0o600)
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(HASetupError, match="FILE_UNSAFE"):
        HAConnectionStore(link).read()
    public = tmp_path / "public"
    public.mkdir(mode=0o755)
    with pytest.raises(HASetupError, match="DIRECTORY_UNSAFE"):
        HAConnectionStore(public / "ha.json").save_new(connection())


class GraphFixture:
    def __init__(self) -> None:
        self.documents: list[CommissioningDocument] = []
        self.nodes: dict[UUID, CanonicalNode] = {}

    def get_node(self, key: UUID) -> CanonicalNode | None:
        return self.nodes.get(key)

    def commission(self, document: CommissioningDocument) -> None:
        self.documents.append(document)
        self.nodes.update({node.canonical_id: node for node in document.nodes})


def test_owner_commissioning_is_separate_idempotent_and_secret_free(tmp_path: Path) -> None:
    graph = GraphFixture()
    fixture_id = UUID("00000000-0000-0000-0000-000000000012")
    graph.nodes[fixture_id] = CanonicalNode(fixture_id, NodeKind.HOUSEHOLD, "Sample Household")
    owner = VerifiedHAOwner("verified-owner", "Owner", "Real home", "America/New_York", SECRET)
    store = HAConnectionStore(tmp_path / "private" / "ha.json")
    household = commission_owner(
        graph,  # type: ignore[arg-type]
        store,
        owner,
        instance_id=INSTANCE,
        base_url="http://configured-ha:8123",
    )
    again = commission_owner(
        graph,  # type: ignore[arg-type]
        store,
        owner,
        instance_id=INSTANCE,
        base_url="http://configured-ha:8123",
    )
    assert again == household != fixture_id
    assert graph.nodes[fixture_id].name == "Sample Household"
    assert graph.nodes[household].name == "Real home"
    assert SECRET not in repr(graph.documents)
    assert SECRET not in repr(owner)
    person = next(node for node in graph.nodes.values() if node.kind == NodeKind.PERSON)
    assert person.metadata["semantic_role"] == "owner"
    assert graph.documents[-1].provider_references[0].external_id == "verified-owner"


class AsyncContext:
    def __init__(self, value: Any) -> None:
        self.value = value

    async def __aenter__(self) -> Any:
        return self.value

    async def __aexit__(self, *args: Any) -> None:
        pass


class HAResponse:
    status = 200

    async def json(self) -> dict[str, str]:
        return {"access_token": "temporary", "refresh_token": "temporary-refresh"}

    async def read(self) -> bytes:
        return b""


class HASession:
    def __init__(self, owner: bool = True) -> None:
        self.owner = owner
        self.messages: list[dict[str, Any]] = []
        self.posts: list[dict[str, Any]] = []
        self.receives = 0

    def post(self, url: str, **kwargs: Any) -> AsyncContext:
        self.posts.append({"url": url, **kwargs})
        return AsyncContext(HAResponse())

    def ws_connect(self, url: str, **kwargs: Any) -> AsyncContext:
        return AsyncContext(self)

    async def send_json(self, message: dict[str, Any]) -> None:
        self.messages.append(message)

    async def receive_json(self) -> dict[str, Any]:
        self.receives += 1
        if self.receives == 1:
            return {"type": "auth_required"}
        if self.receives == 2:
            return {"type": "auth_ok"}
        message = self.messages[-1]
        values: dict[str, Any] = {
            "auth/current_user": {"id": "verified-owner", "name": "Owner", "is_owner": self.owner},
            "get_config": {"location_name": "Real home", "time_zone": "America/New_York"},
            "auth/long_lived_access_token": SECRET,
        }
        return {"id": message["id"], "success": True, "result": values[message["type"]]}


@pytest.mark.parametrize("is_owner", [False, True])
def test_oauth_setup_requires_real_owner_and_revokes_temporary_grant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    is_owner: bool,
) -> None:
    session = HASession(is_owner)
    monkeypatch.setattr("anima_ha.ui_api.ClientSession", lambda **kwargs: AsyncContext(session))
    oauth = HomeAssistantOAuth(
        UIConfig(
            ha_base_url="http://configured-ha:8123",
            ha_client_id="http://localhost:18090",
        )
    )
    store = HAConnectionStore(tmp_path / "private" / "ha.json")
    if is_owner:
        owner = asyncio.run(oauth.connect_owner("synthetic-code", store))
        assert owner.token == SECRET
        assert owner.household_name == "Real home"
    else:
        with pytest.raises(UIAuthError, match="OWNER_REQUIRED"):
            asyncio.run(oauth.connect_owner("synthetic-code", store))
        assert not any(item["type"] == "auth/long_lived_access_token" for item in session.messages)
    assert session.posts[-1]["data"] == {"action": "revoke", "token": "temporary-refresh"}
    assert store.read() is None  # OAuth verification itself never writes authority.


def test_setup_is_explicit_browser_bound_and_status_has_no_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANIMA_HA_CONNECTION_FILE", str(tmp_path / "private" / "ha.json"))
    service = UIService(
        config=UIConfig(
            ha_base_url="http://configured-ha:8123",
            ha_client_id="http://localhost:18090",
            ha_redirect_uri="http://localhost:18090/auth/callback",
        )
    )
    client = TestClient(create_app(service), follow_redirects=False)
    assert client.get("/api/v1/setup/status").json() == {
        "state": "SETUP_REQUIRED",
        "available": True,
    }
    assert client.get("/api/v1/connection").status_code == 401
    client.get("/auth/login?connect=1")
    state = next(iter(service._oauth_connection_states))
    other = TestClient(create_app(service), follow_redirects=False)
    rejected = other.get("/auth/callback", params={"state": state, "code": "synthetic-code"})
    assert rejected.status_code == 400
    assert rejected.json()["detail"] == "OAUTH_STATE_REJECTED"
    assert not service._oauth_connection_states
    assert "token" not in json.dumps(service.connection_status()).lower()


def test_multiple_tabs_bootstrap_does_not_invalidate_session_csrf() -> None:
    service = UIService(config=UIConfig(test_auth_enabled=True))
    client = TestClient(create_app(service), follow_redirects=False)
    login = client.get("/auth/login")
    client.get(login.headers["location"])
    first = client.get("/api/v1/bootstrap").json()["csrf_token"]
    second = client.get("/api/v1/bootstrap").json()["csrf_token"]
    assert first == second
    changed = client.put(
        "/api/v1/settings",
        json={"payload": {"appearance": "light"}},
        headers={"Origin": "http://testserver", "X-Anima-CSRF": first},
    )
    assert changed.status_code == 200
    other = TestClient(create_app(service), follow_redirects=False)
    login = other.get("/auth/login")
    other.get(login.headers["location"])
    assert other.get("/api/v1/bootstrap").json()["csrf_token"] != first
    assert (
        other.put(
            "/api/v1/settings",
            json={"payload": {"appearance": "night"}},
            headers={"Origin": "http://testserver", "X-Anima-CSRF": first},
        ).status_code
        == 403
    )
