"""Expanded frozen schema catalogues do not enlarge household-data responses."""

import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import pytest


def test_catalogue_limit_is_route_specific_and_bounded() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "integrations/sentry/anima-household/anima_household_client.py"
    )
    spec = importlib.util.spec_from_file_location("catalogue_transport_client", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    request = str(uuid4())
    route = f"/v1/requests/{request}/tools"
    assert module._response_limit(route) == 128 * 1024
    for path in [
        f"/v1/requests/{request}/invoke",
        f"/v1/requests/{request}/context",
        "/v1/requests/not-a-uuid/tools",
        route + "?extra=1",
        route + "/",
    ]:
        assert module._response_limit(path) == 64 * 1024
    raw = json.dumps({"tools": [{"description": "x" * 76000}]}).encode()
    assert module._decode_response(raw, 200, limit=module._response_limit(route))["tools"]
    with pytest.raises(module.AnimaHouseholdError, match="transport limit"):
        module._decode_response(raw, 200)
    with pytest.raises(module.AnimaHouseholdError, match="transport limit"):
        module._decode_response(b"x" * (128 * 1024 + 1), 200, limit=module._response_limit(route))
