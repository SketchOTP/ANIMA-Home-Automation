#!/usr/bin/env python3
"""Verify that ANIMA's bounded owner surface matches its declared support matrix."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from anima_ha.ui_api import UIConfig, UIService, create_app

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "config" / "owner_support_matrix.json"
REQUIRED_INVARIANTS = {
    "ha_frontend_required": False,
    "browser_direct_ha": False,
    "browser_direct_provider": False,
    "raw_admin_surface": False,
}
PROHIBITED_RAW_PATH_PARTS = ("/sql", "/shell", "/yaml", "/ha-service", "/raw-http")


def _declared_routes(matrix: dict[str, Any]) -> list[str]:
    routes: list[str] = []
    for domain in matrix.get("domains", []):
        if not isinstance(domain, dict):
            raise AssertionError("support-matrix domain must be an object")
        if not all(str(domain.get(field, "")).strip() for field in ("id", "surface", "boundary")):
            raise AssertionError("every support-matrix domain needs id, surface, and boundary")
        domain_routes = domain.get("routes")
        if not isinstance(domain_routes, list) or not domain_routes:
            raise AssertionError(f"support-matrix domain {domain.get('id')} has no routes")
        routes.extend(str(route) for route in domain_routes)
    return routes


def _application_routes() -> list[str]:
    app = create_app(UIService(config=UIConfig(test_auth_enabled=True)))
    routes: list[str] = []
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None)
        if not path or not methods or path == "/openapi.json":
            continue
        for method in sorted(set(methods) - {"HEAD", "OPTIONS"}):
            routes.append(f"{method} {path}")
    return routes


def verify() -> dict[str, Any]:
    raw = MATRIX_PATH.read_bytes()
    matrix = json.loads(raw)
    if matrix.get("schema_version") != 1:
        raise AssertionError("unsupported owner support-matrix schema")
    if matrix.get("invariants") != REQUIRED_INVARIANTS:
        raise AssertionError("owner support-matrix invariants changed or are incomplete")

    declared = _declared_routes(matrix)
    actual = _application_routes()
    if len(declared) != len(set(declared)):
        raise AssertionError("owner support matrix contains duplicate routes")
    missing = sorted(set(actual) - set(declared))
    stale = sorted(set(declared) - set(actual))
    if missing or stale:
        raise AssertionError(f"owner support matrix mismatch: missing={missing}, stale={stale}")
    prohibited = sorted(
        route
        for route in declared
        if any(part in route.casefold() for part in PROHIBITED_RAW_PATH_PARTS)
    )
    if prohibited:
        raise AssertionError(f"raw administration routes are prohibited: {prohibited}")

    return {
        "status": "PASSED",
        "schema_version": matrix["schema_version"],
        "route_count": len(declared),
        "domain_count": len(matrix["domains"]),
        "invariants": matrix["invariants"],
        "matrix_sha256": hashlib.sha256(raw).hexdigest(),
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
