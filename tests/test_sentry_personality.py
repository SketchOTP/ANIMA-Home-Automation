from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from threading import Thread
from typing import Any, cast
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from anima_ha.db.migrate import migrate
from anima_ha.sentry_personality import (
    MAX_PROFILE_TEXT,
    SentryPersonalityConflict,
    SentryPersonalityStore,
    validate_personality_profile,
)
from anima_ha.sentry_service import (
    CoreSentryHTTPService,
    SentryServicePrincipal,
    _Handler,
    _UnixHTTPServer,
)
from anima_ha.ui_api import UIConfig, UIService, create_app


def authenticated_client() -> tuple[TestClient, str]:
    client = TestClient(create_app(UIService(config=UIConfig(test_auth_enabled=True))))
    login = client.get("/auth/login", follow_redirects=False)
    callback = client.get(login.headers["location"], follow_redirects=False)
    return client, callback.headers["x-anima-csrf"]


def mutation(client: TestClient, csrf: str, operation: str, payload: dict[str, Any]) -> Any:
    return client.post(
        f"/api/v1/sentry/personality-profiles/{operation}",
        json={"payload": payload},
        headers={"Origin": "http://testserver", "X-Anima-CSRF": csrf},
    )


def test_profile_validation_is_free_form_but_bounded() -> None:
    assert validate_personality_profile(
        {"name": "Calm host", "profile_text": "Warm, curious, and lightly witty."}
    ) == {"name": "Calm host", "profile_text": "Warm, curious, and lightly witty."}
    with pytest.raises(ValueError):
        validate_personality_profile({"name": "", "profile_text": "Warm"})
    with pytest.raises(ValueError):
        validate_personality_profile({"name": "Host", "profile_text": "x" * (MAX_PROFILE_TEXT + 1)})
    with pytest.raises(ValueError):
        validate_personality_profile({"name": "Host", "profile_text": "bad\x00text"})


def test_scoped_sentry_client_reads_only_the_active_household_profile(tmp_path: Path) -> None:
    household_id = uuid4()
    token = "p" * 48
    token_file = tmp_path / "client.token"
    token_file.write_text(token, encoding="utf-8")
    token_file.chmod(0o600)
    observed: list[Any] = []

    class Store:
        def active(self, household: Any) -> dict[str, Any]:
            observed.append(household)
            return {
                "status": "ACTIVE",
                "profile_id": str(uuid4()),
                "name": "Warm",
                "profile_text": "Warm and concise.",
                "version": str(uuid4()),
            }

    principal = SentryServicePrincipal.from_secret(
        client_id="test-personality-client",
        household_id=household_id,
        provider_id="sentry",
        token=token,
    )
    socket_path = tmp_path / "core.sock"
    server = _UnixHTTPServer(str(socket_path), _Handler)  # type: ignore[arg-type]
    server.service = CoreSentryHTTPService(
        cast(Any, object()),
        lambda: token,
        service_principal=principal,
        personality_store=cast(Any, Store()),
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client_path = (
            Path(__file__).parents[1]
            / "integrations/sentry/anima-household/anima_household_client.py"
        )
        spec = importlib.util.spec_from_file_location("personality_test_client", client_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.AnimaHouseholdClient(
            str(socket_path), str(token_file)
        ).personality_profile()
        assert result["name"] == "Warm"
        assert observed == [household_id]
    finally:
        server.shutdown()
        server.server_close()


def test_owner_api_manages_multiple_versioned_profiles() -> None:
    client, csrf = authenticated_client()
    first = mutation(
        client,
        csrf,
        "create",
        {"name": "Warm", "profile_text": "Warm and conversational."},
    )
    assert first.status_code == 200
    first_profile = first.json()["profiles"]["items"][0]
    assert first_profile["active"] is False

    second = mutation(
        client,
        csrf,
        "create",
        {"name": "Formal", "profile_text": "Reserved and concise."},
    )
    second_profile = next(
        item for item in second.json()["profiles"]["items"] if item["name"] == "Formal"
    )
    assert second_profile["active"] is False

    updated = mutation(
        client,
        csrf,
        "update",
        {
            "profile_id": second_profile["profile_id"],
            "expected_version": second_profile["version"],
            "name": "Formal",
            "profile_text": "Reserved, concise, and reassuring.",
        },
    )
    assert updated.status_code == 200
    revised = next(item for item in updated.json()["profiles"]["items"] if item["name"] == "Formal")
    assert revised["profile_text"].endswith("reassuring.")

    stale = mutation(
        client,
        csrf,
        "activate",
        {
            "profile_id": second_profile["profile_id"],
            "expected_version": second_profile["version"],
        },
    )
    assert stale.status_code == 409

    activated = mutation(
        client,
        csrf,
        "activate",
        {"profile_id": revised["profile_id"], "expected_version": revised["version"]},
    )
    active = next(item for item in activated.json()["profiles"]["items"] if item["active"])
    assert active["name"] == "Formal"

    default = mutation(client, csrf, "activate_default", {})
    assert default.status_code == 200
    assert default.json()["profiles"]["fallback_active"] is True
    assert all(item["active"] is False for item in default.json()["profiles"]["items"])

    saved_after_default = next(
        item
        for item in default.json()["profiles"]["items"]
        if item["profile_id"] == revised["profile_id"]
    )
    reactivated = mutation(
        client,
        csrf,
        "activate",
        {
            "profile_id": saved_after_default["profile_id"],
            "expected_version": saved_after_default["version"],
        },
    )
    active = next(item for item in reactivated.json()["profiles"]["items"] if item["active"])

    deleted = mutation(
        client,
        csrf,
        "delete",
        {"profile_id": active["profile_id"], "expected_version": active["version"]},
    )
    assert deleted.status_code == 200
    assert deleted.json()["profiles"]["fallback_active"] is True


@pytest.fixture(scope="module")
def database_url() -> str:
    url = os.environ.get("ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL")
    if not url:
        pytest.skip("requires disposable ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL")
    with psycopg.connect(url) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "anima_family_routines_test",
        )
    migrate(url, 5)
    return url


def test_postgres_profiles_survive_store_reconstruction_and_are_household_scoped(
    database_url: str,
) -> None:
    household = uuid4()
    other_household = uuid4()
    store = SentryPersonalityStore(database_url)
    created = store.create(
        household,
        {"name": "Night watch", "profile_text": "Calm, direct, and reassuring."},
    )
    assert created["active"] is False
    assert SentryPersonalityStore(database_url).active(household)["status"] == "DEFAULT"
    assert SentryPersonalityStore(database_url).active(other_household)["status"] == "DEFAULT"

    with pytest.raises(SentryPersonalityConflict):
        store.update(
            household,
            {
                "profile_id": created["profile_id"],
                "expected_version": str(uuid4()),
                "name": "Night watch",
                "profile_text": "Changed",
            },
        )

    activated = store.activate(
        household,
        {"profile_id": created["profile_id"], "expected_version": created["version"]},
    )
    assert activated["active"] is True
    default = store.mutate(household, "activate_default", {})
    assert default["active_profile_id"] is None
    assert default["fallback_active"] is True
    assert default["items"][0]["active"] is False
