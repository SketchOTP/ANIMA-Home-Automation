"""Live synthetic evidence for the no-secret Phase 11 providers."""

from __future__ import annotations

import os
from uuid import UUID, uuid4

from anima_ha.external import (
    BoundedHttpClient,
    BraveProvider,
    GoogleCalendarCredentialProvider,
    GoogleCalendarProvider,
    NtfyProvider,
    OpenMeteoProvider,
    TheMealDBProvider,
    external_resource_gates,
)
from anima_ha.plugins import ProviderExecutionContext


def main() -> int:
    audits = []
    weather = OpenMeteoProvider(
        BoundedHttpClient(
            provider="open-meteo",
            base_url="https://api.open-meteo.com",
            allowed_hosts=("api.open-meteo.com",),
            audit_sink=audits,
        )
    ).invoke(
        "get",
        {"latitude": 40.0, "longitude": -74.0, "timezone": "UTC", "forecast_days": 1},
        10,
    )
    assert weather["trust"] == "EXTERNAL_UNTRUSTED"
    print("open_meteo_live_synthetic=PASS")

    recipe = TheMealDBProvider(
        BoundedHttpClient(
            provider="themealdb",
            base_url="https://www.themealdb.com",
            allowed_hosts=("www.themealdb.com",),
            audit_sink=audits,
        )
    ).invoke("search", {"query": "pasta"}, 10)
    assert recipe["trust"] == "EXTERNAL_UNTRUSTED"
    assert isinstance(recipe["data"]["recipes"], list)
    print("themealdb_live_synthetic=PASS")

    topic = "anima-phase11-" + uuid4().hex
    notification = NtfyProvider(
        BoundedHttpClient(
            provider="ntfy",
            base_url="https://ntfy.sh",
            allowed_hosts=("ntfy.sh",),
            audit_sink=audits,
        ),
        topic,
    ).invoke_with_context(
        "send",
        {"title": "ANIMA Phase 11 synthetic", "message": "synthetic no-household-data proof"},
        10,
        ProviderExecutionContext(UUID(int=1), "anima-phase11-synthetic-notification"),
    )
    assert notification["accepted"] is True
    print("ntfy_live_synthetic_no_cache=PASS")

    gates = external_resource_gates(dict(os.environ))
    for name, status in sorted(gates.items()):
        print(f"{name}={status}")
    if gates["EXTERNAL_RESOURCE_GATE_BRAVE_SEARCH"] == "AVAILABLE":
        brave = BraveProvider(
            BoundedHttpClient(
                provider="brave",
                base_url="https://api.search.brave.com",
                allowed_hosts=("api.search.brave.com",),
                audit_sink=audits,
                credential_reference="BRAVE_SEARCH_API_KEY",
            ),
            os.environ["BRAVE_SEARCH_API_KEY"],
        )
        for label, operation, arguments in (
            (
                "brave_web_live",
                "search",
                {"query": "synthetic Phase 11 public web qualification"},
            ),
            (
                "brave_places_live",
                "search_places",
                {"query": "public library Newark NJ", "count": 3},
            ),
            (
                "brave_products_live",
                "search_products",
                {"query": "synthetic reusable water bottle product discovery", "count": 3},
            ),
        ):
            result = brave.invoke(operation, arguments, 10)
            assert result["trust"] == "EXTERNAL_UNTRUSTED"
            print(f"{label}=PASS class=LIVE_CREDENTIALED")
    else:
        for label in ("brave_web_live", "brave_places_live", "brave_products_live"):
            print(f"{label}=EXTERNAL_RESOURCE_GATE_BRAVE_SEARCH class=EXTERNAL_RESOURCE_GATE")

    google_names = (
        "GOOGLE_CALENDAR_CLIENT_ID",
        "GOOGLE_CALENDAR_CLIENT_SECRET",
        "GOOGLE_CALENDAR_REFRESH_TOKEN",
    )
    if all(os.environ.get(name, "").strip() for name in google_names):
        calendar = GoogleCalendarProvider(
            BoundedHttpClient(
                provider="google-calendar",
                base_url="https://www.googleapis.com",
                allowed_hosts=("www.googleapis.com",),
                audit_sink=audits,
                credential_reference="GOOGLE_CALENDAR_REFRESH_TOKEN",
            ),
            GoogleCalendarCredentialProvider(
                os.environ["GOOGLE_CALENDAR_CLIENT_ID"],
                os.environ["GOOGLE_CALENDAR_CLIENT_SECRET"],
                os.environ["GOOGLE_CALENDAR_REFRESH_TOKEN"],
            ),
            os.environ.get("GOOGLE_CALENDAR_ID", "primary"),
        )
        context = ProviderExecutionContext(UUID(int=3), "anima-phase11-calendar-live")
        listed = calendar.invoke("list_events", {"count": 5}, 10)
        assert listed["trust"] == "EXTERNAL_UNTRUSTED"
        print("google_calendar_list_live=PASS class=LIVE_CREDENTIALED")
        created = calendar.invoke_with_context(
            "create_event",
            {
                "summary": "ANIMA Phase 11 synthetic qualification",
                "start": "2026-09-01T10:00:00Z",
                "end": "2026-09-01T10:05:00Z",
            },
            10,
            context,
        )
        assert created["readback_verified"] is True
        print("google_calendar_create_readback_live=PASS class=LIVE_CREDENTIALED")
    else:
        print(
            "google_calendar_list_live=EXTERNAL_RESOURCE_GATE_GOOGLE_CALENDAR "
            "class=EXTERNAL_RESOURCE_GATE"
        )
        print(
            "google_calendar_create_readback_live=EXTERNAL_RESOURCE_GATE_GOOGLE_CALENDAR "
            "class=EXTERNAL_RESOURCE_GATE"
        )
    print(f"external_audit_records={len(audits)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
