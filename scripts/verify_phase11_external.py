"""Bounded Phase 11 live and deterministic evidence harness."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from anima_ha.calendar import CalendarService, InMemoryCalendarStore
from anima_ha.external import (
    BoundedHttpClient,
    LocalServiceClient,
    OpenMeteoProvider,
    OverpassProvider,
    SearXNGProvider,
    TheMealDBProvider,
    external_resource_gates,
)
from anima_ha.plugins import InvocationContext
from anima_ha.policy import RequestOrigin


def _context(key: str) -> InvocationContext:
    return InvocationContext(
        household_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        principal_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        episode_id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        tool_request_id=uuid4(),
        ordinal=1,
        system_idempotency_key=key,
        origin=RequestOrigin.TESTING,
    )


def main() -> int:
    audits = []
    weather = OpenMeteoProvider(
        BoundedHttpClient(
            provider="open-meteo",
            base_url="https://api.open-meteo.com",
            allowed_hosts=("api.open-meteo.com",),
            audit_sink=audits,
        )
    ).invoke("get", {"latitude": 40.0, "longitude": -74.0, "timezone": "UTC"}, 10)
    assert weather["trust"] == "EXTERNAL_UNTRUSTED"
    print("open_meteo_live_synthetic=PASS class=LIVE_PUBLIC_SYNTHETIC")

    recipe = TheMealDBProvider(
        BoundedHttpClient(
            provider="themealdb",
            base_url="https://www.themealdb.com",
            allowed_hosts=("www.themealdb.com",),
            audit_sink=audits,
        )
    ).invoke("search", {"query": "pasta"}, 10)
    assert recipe["trust"] == "EXTERNAL_UNTRUSTED"
    print("themealdb_live_synthetic=PASS class=LIVE_PUBLIC_SYNTHETIC")

    start = datetime(2026, 9, 1, 10, tzinfo=UTC)
    calendar = CalendarService(InMemoryCalendarStore())
    event = calendar.create(
        context=_context("phase11-calendar"),
        arguments={
            "title": "Phase 11 local synthetic event",
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(minutes=30)).isoformat(),
            "timezone": "UTC",
        },
    )
    assert (
        calendar.get(household_id=event.household_id, event_id=event.event_id).event_id
        == event.event_id
    )
    print("local_calendar_crud=PASS class=DETERMINISTIC_INTEGRATION")

    gates = external_resource_gates(dict(os.environ))
    discovery_url = os.environ.get("ANIMA_SEARXNG_URL", "http://127.0.0.1:18888")
    discovery_host = os.environ.get("ANIMA_SEARXNG_HOST", "127.0.0.1")
    try:
        search_client = LocalServiceClient(
            provider="searxng",
            base_url=discovery_url,
            service_host=discovery_host,
            audit_sink=audits,
        )
        search = SearXNGProvider(search_client)
        for label, operation, query in (
            ("searxng_web_live", "search", "synthetic public web qualification"),
            ("searxng_products_live", "search_products", "synthetic reusable bottle product"),
        ):
            result = search.invoke(operation, {"query": query, "count": 3}, 10)
            assert result["trust"] == "EXTERNAL_UNTRUSTED"
            print(f"{label}=PASS class=LIVE_PUBLIC_SYNTHETIC")
    except Exception as exc:
        print(f"searxng_web_live=EXTERNAL_RESOURCE_GATE detail={type(exc).__name__}")
        print(f"searxng_products_live=EXTERNAL_RESOURCE_GATE detail={type(exc).__name__}")

    try:
        overpass = OverpassProvider(
            BoundedHttpClient(
                provider="overpass",
                base_url="https://overpass-api.de",
                allowed_hosts=("overpass-api.de",),
                audit_sink=audits,
            )
        )
        result = overpass.invoke(
            "search_places",
            {
                "category": "restaurant",
                "latitude": 40.0,
                "longitude": -74.0,
                "radius_m": 1000,
                "count": 3,
            },
            15,
        )
        assert result["trust"] == "EXTERNAL_UNTRUSTED"
        print("overpass_places_live=PASS class=LIVE_PUBLIC_SYNTHETIC")
    except Exception as exc:
        print(f"overpass_places_live=EXTERNAL_RESOURCE_GATE detail={type(exc).__name__}")

    print(f"EXTERNAL_RESOURCE_GATE_SEARXNG_SEARCH={gates['EXTERNAL_RESOURCE_GATE_SEARXNG_SEARCH']}")
    print(f"EXTERNAL_RESOURCE_GATE_OVERPASS={gates['EXTERNAL_RESOURCE_GATE_OVERPASS']}")
    print(f"external_audit_records={len(audits)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
