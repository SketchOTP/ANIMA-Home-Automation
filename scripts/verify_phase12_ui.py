"""Deterministic Phase 12 local-interface evidence harness."""

from __future__ import annotations

from fastapi.testclient import TestClient

from anima_ha.ui_api import UIConfig, UIService, create_app


def main() -> int:
    service = UIService(config=UIConfig(test_auth_enabled=True))
    client = TestClient(create_app(service), follow_redirects=False)

    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "anima-ui", "version": "0.1.0"}
    assert client.get("/api/v1/home").status_code == 401
    print("ui_health_and_unauthenticated_boundary=PASS class=DETERMINISTIC_INTEGRATION")

    login = client.get("/auth/login")
    assert login.status_code == 307
    callback = client.get(login.headers["location"])
    assert callback.status_code == 307
    cookie = client.cookies.get("anima_session")
    assert cookie is not None and "." in cookie
    assert "HttpOnly" in callback.headers["set-cookie"]
    assert "SameSite=strict" in callback.headers["set-cookie"]

    bootstrap = client.get("/api/v1/bootstrap")
    assert bootstrap.status_code == 200
    bootstrap_body = bootstrap.json()
    assert bootstrap_body["identity"]["assurance"] == "AUTHENTICATED"
    assert client.get("/api/v1/home").status_code == 200
    print("ui_oauth_test_mapping_and_semantic_bootstrap=PASS class=DETERMINISTIC_INTEGRATION")

    csrf = bootstrap_body["csrf_token"]
    blocked = client.post("/api/v1/conversation", json={"text": "hello"})
    assert blocked.status_code == 403
    wrong_origin = client.post(
        "/api/v1/conversation",
        json={"text": "hello"},
        headers={"X-Anima-CSRF": csrf, "Origin": "https://untrusted.example"},
    )
    assert wrong_origin.status_code == 403
    conversation = client.post(
        "/api/v1/conversation",
        json={"text": "What is happening at home?"},
        headers={"X-Anima-CSRF": csrf, "Origin": "http://testserver"},
    )
    assert conversation.status_code == 200
    assert conversation.json()["trace"]["origin"] == "DIRECT_USER"
    print("ui_csrf_origin_and_conversation_boundary=PASS class=E3_TARGET_TESTED")

    home = client.get("/api/v1/home").json()
    assert set(home) == {
        "household",
        "security",
        "presence",
        "weather",
        "calendar",
        "tasks",
        "activity",
        "voice",
        "attention",
        "controls",
    }
    assert all("anima_" not in str(value) for value in home.values())
    print("ui_anima_owned_view_model_no_internal_rows=PASS class=DETERMINISTIC_INTEGRATION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
