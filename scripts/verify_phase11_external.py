"""Live synthetic evidence for the no-secret Phase 11 providers."""

from __future__ import annotations

import os
from uuid import UUID, uuid4

from anima_ha.external import (
    BoundedHttpClient,
    BraveProvider,
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
        result = brave.invoke("search", {"query": "synthetic Phase 11 qualification"}, 10)
        assert result["trust"] == "EXTERNAL_UNTRUSTED"
        print("brave_live_credentialed=PASS")
    else:
        print("brave_live_credentialed=EXTERNAL_RESOURCE_GATE")
    print(f"external_audit_records={len(audits)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
