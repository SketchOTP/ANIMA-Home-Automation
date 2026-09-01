"""Bounded Phase 11 live and deterministic evidence harness."""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from anima_ha.calendar import CalendarService, InMemoryCalendarStore
from anima_ha.external import (
    WALMART_SECRET_NAMES,
    BoundedHttpClient,
    LocalServiceClient,
    OpenMeteoProvider,
    OverpassProvider,
    SearXNGProvider,
    TheMealDBProvider,
    external_plugin,
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-phase11-targets",
        action="store_true",
        help="fail if required live SearXNG or Overpass target evidence is unavailable",
    )
    parser.add_argument(
        "--require-walmart-products",
        action="store_true",
        help="fail if credentialed Walmart product evidence is unavailable",
    )
    args = parser.parse_args()
    failures: list[str] = []
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
        try:
            result = search.invoke("search", {"query": "Python", "count": 3}, 10)
            assert result["trust"] == "EXTERNAL_UNTRUSTED"
            results = result["data"]["results"]
            if not results:
                raise AssertionError("searxng_web_live returned no results")
            if not all(item.get("title") and item.get("url") for item in results):
                raise AssertionError("searxng_web_live returned an incomplete source record")
            print(
                f"searxng_web_live_results={len(results)} "
                f"engines={result['provider_metadata']['configured_engines']} "
                f"unresponsive={result['provider_metadata']['unresponsive_engines']}"
            )
            print("searxng_web_live=PASS class=LIVE_PUBLIC_SYNTHETIC")
        except Exception as exc:
            print(f"searxng_web_live=EXTERNAL_RESOURCE_GATE detail={type(exc).__name__}")
            if args.require_phase11_targets:
                failures.append(f"searxng_web_live: {type(exc).__name__}")
    except Exception as exc:
        print(f"searxng_web_live=EXTERNAL_RESOURCE_GATE detail={type(exc).__name__}")
        if args.require_phase11_targets:
            failures.append(f"SearXNG service: {type(exc).__name__}")

    walmart_env = {name: os.environ[name] for name in WALMART_SECRET_NAMES if os.environ.get(name)}
    if all(walmart_env.get(name, "").strip() for name in WALMART_SECRET_NAMES):
        walmart_runtime = None
        try:
            _, walmart_runtime = external_plugin("anima.external.shopping", audit_sink=audits)
            walmart_runtime.start(walmart_env)
            for query in ("wireless headphones", "air fryer"):
                result = walmart_runtime.invoke(
                    "search_products", {"query": query, "count": 10}, 10
                )
                assert result["trust"] == "EXTERNAL_UNTRUSTED"
                products = result["data"]["products"]
                references = {item["provider_reference"] for item in products}
                assert len(products) >= 3 and len(references) == len(products)
                print(f"walmart_products_live_query={query!r} results={len(products)}")
            print("walmart_products_live=PASS class=LIVE_CREDENTIALED")
        except Exception as exc:
            print(f"walmart_products_live=EXTERNAL_RESOURCE_GATE detail={type(exc).__name__}")
            if args.require_walmart_products:
                failures.append(f"walmart_products_live: {type(exc).__name__}")
        finally:
            if walmart_runtime is not None:
                walmart_runtime.stop()
    else:
        print("walmart_products_live=EXTERNAL_RESOURCE_GATE detail=credentials_missing")
        if args.require_walmart_products:
            failures.append("walmart_products_live: credentials_missing")

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
        if args.require_phase11_targets:
            failures.append(f"Overpass target evidence: {type(exc).__name__}")

    print(f"EXTERNAL_RESOURCE_GATE_SEARXNG_SEARCH={gates['EXTERNAL_RESOURCE_GATE_SEARXNG_SEARCH']}")
    print(f"EXTERNAL_RESOURCE_GATE_OVERPASS={gates['EXTERNAL_RESOURCE_GATE_OVERPASS']}")
    print(
        f"EXTERNAL_RESOURCE_GATE_WALMART_PRODUCT_SEARCH={gates['EXTERNAL_RESOURCE_GATE_WALMART_PRODUCT_SEARCH']}"
    )
    print(f"external_audit_records={len(audits)}")
    if failures:
        for failure in failures:
            print(f"STRICT_TARGET_FAILURE={failure}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
