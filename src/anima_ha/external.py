"""Bounded external-by-intent capability adapters.

External providers stop at this module.  Core receives small normalized
envelopes, provider content is explicitly untrusted, and no model argument
can select a host, credential, topic, or arbitrary HTTP operation.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx

from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.plugins import (
    ExternalContentTrust,
    Idempotency,
    PluginManifest,
    ProviderExecutionContext,
    RuntimeKind,
    TrustClass,
)

MAX_RESPONSE_BYTES = 1_048_576
MAX_QUERY_LENGTH = 400
MAX_RESULT_COUNT = 10


class ExternalProviderError(RuntimeError):
    """A bounded provider or transport failure."""


class ExternalProviderUnavailable(ExternalProviderError):
    """A provider cannot run because a credential or configuration is absent."""


@dataclass(frozen=True, slots=True)
class ExternalResult:
    provider: str
    operation: str
    retrieved_at: datetime
    trust: ExternalContentTrust = ExternalContentTrust.EXTERNAL_UNTRUSTED
    freshness: str = "LIVE"
    attribution: str = ""
    sources: tuple[dict[str, str], ...] = ()
    data: dict[str, Any] = field(default_factory=dict)
    provider_metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "operation": self.operation,
            "retrieved_at": self.retrieved_at.isoformat(),
            "trust": self.trust.value,
            "freshness": self.freshness,
            "attribution": self.attribution,
            "sources": [dict(item) for item in self.sources],
            "data": self.data,
            "provider_metadata": self.provider_metadata,
        }


@dataclass(frozen=True, slots=True)
class ExternalRequestAudit:
    provider: str
    operation: str
    timestamp: datetime
    request_fields: tuple[str, ...]
    payload_digest: str
    outbound_bytes: int
    response_bytes: int
    latency_ms: float
    status: int | None
    result_class: str
    credential_reference: str | None = None


class AuditSink(Protocol):
    def append(self, item: ExternalRequestAudit) -> Any: ...


class ExternalAuditJournalSink:
    """Adapt bounded external request audits to the append-only event journal."""

    def __init__(self, journal: Any) -> None:
        self.journal = journal

    def append(self, item: ExternalRequestAudit) -> Any:
        event = EventEnvelope.create(
            event_id=str(uuid4()),
            event_type="external.request.audit",
            source="anima.external",
            subject_key=f"{item.provider}/{item.operation}",
            occurred_at=item.timestamp,
            payload={
                "provider": item.provider,
                "operation": item.operation,
                "request_fields": list(item.request_fields),
                "payload_digest": item.payload_digest,
                "outbound_bytes": item.outbound_bytes,
                "response_bytes": item.response_bytes,
                "latency_ms": item.latency_ms,
                "status": item.status,
                "result_class": item.result_class,
                "credential_reference": item.credential_reference,
            },
            importance=EventImportance.NORMAL,
            delivery_class=DeliveryClass.BEST_EFFORT,
        )
        return self.journal.append(event)


class BoundedHttpClient:
    """Fixed-host HTTP transport with bounded body, timeout, and audit."""

    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        allowed_hosts: tuple[str, ...],
        audit_sink: AuditSink | list[ExternalRequestAudit] | None = None,
        credential_reference: str | None = None,
        timeout: float = 10.0,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        transport: httpx.BaseTransport | None = None,
        require_https: bool = True,
        allow_private: bool = False,
    ) -> None:
        parsed = httpx.URL(base_url)
        if parsed.host is None or (require_https and parsed.scheme != "https"):
            raise ValueError("provider base URL has an invalid scheme or host")
        if parsed.host not in allowed_hosts or (
            not allow_private and not self._safe_host(parsed.host)
        ):
            raise ValueError("base URL host is not allowlisted")
        self.provider = provider
        self.base_url = str(parsed).rstrip("/")
        self.allowed_hosts = frozenset(allowed_hosts)
        self.audit_sink = audit_sink
        self.credential_reference = credential_reference
        self.max_response_bytes = max_response_bytes
        self.allow_private = allow_private
        self.client = httpx.Client(
            base_url=self.base_url,
            follow_redirects=False,
            timeout=httpx.Timeout(timeout),
            transport=transport,
        )

    @staticmethod
    def _safe_host(host: str | None) -> bool:
        if host is None:
            return False
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return host not in {"localhost", "localhost.localdomain"}
        return not (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_unspecified
        )

    def _record(
        self,
        *,
        operation: str,
        fields: tuple[str, ...],
        request_payload: Any,
        outbound_bytes: int,
        response_bytes: int,
        latency_ms: float,
        status: int | None,
        result_class: str,
    ) -> None:
        if self.audit_sink is None:
            return
        item = ExternalRequestAudit(
            self.provider,
            operation,
            datetime.now(UTC),
            tuple(sorted(fields)),
            hashlib.sha256(
                json.dumps(request_payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            outbound_bytes,
            response_bytes,
            latency_ms,
            status,
            result_class,
            self.credential_reference,
        )
        if isinstance(self.audit_sink, list):
            self.audit_sink.append(item)
        else:
            self.audit_sink.append(item)

    def request(
        self,
        *,
        operation: str,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        if not path.startswith("/") or "?" in path or "//" in path:
            raise ValueError("provider adapters must use a fixed relative path")
        url = httpx.URL(self.base_url + path)
        if url.host not in self.allowed_hosts or (
            not self.allow_private and not self._safe_host(url.host)
        ):
            raise ValueError("external request host is not allowlisted")
        if method.upper() not in {"GET", "POST"}:
            raise ValueError("external method is not allowed")
        payload = {"path": path, "params": params or {}, "json": json_body or {}}
        outbound_bytes = len(json.dumps(payload, sort_keys=True).encode())
        started = time.monotonic()
        response: httpx.Response | None = None
        response_bytes = 0
        try:
            response = self.client.request(
                method.upper(), path, params=params, json=json_body, headers=headers
            )
            chunks: list[bytes] = []
            for chunk in response.iter_bytes():
                response_bytes += len(chunk)
                if response_bytes > self.max_response_bytes:
                    raise ExternalProviderError("provider response exceeds size bound")
                chunks.append(chunk)
            body = b"".join(chunks)
            if response.status_code < 200 or response.status_code >= 300:
                self._record(
                    operation=operation,
                    fields=tuple((params or {}).keys()) + tuple((json_body or {}).keys()),
                    request_payload=payload,
                    outbound_bytes=outbound_bytes,
                    response_bytes=response_bytes,
                    latency_ms=(time.monotonic() - started) * 1000,
                    status=response.status_code,
                    result_class="HTTP_ERROR",
                )
                raise ExternalProviderError(f"provider HTTP {response.status_code}")
            try:
                value = json.loads(body or b"{}")
            except json.JSONDecodeError as exc:
                raise ExternalProviderError("provider returned invalid JSON") from exc
            if not isinstance(value, dict):
                raise ExternalProviderError("provider response must be a JSON object")
            self._record(
                operation=operation,
                fields=tuple((params or {}).keys()) + tuple((json_body or {}).keys()),
                request_payload=payload,
                outbound_bytes=outbound_bytes,
                response_bytes=response_bytes,
                latency_ms=(time.monotonic() - started) * 1000,
                status=response.status_code,
                result_class="SUCCESS",
            )
            return response.status_code, value
        except (httpx.TimeoutException, TimeoutError) as exc:
            self._record(
                operation=operation,
                fields=tuple((params or {}).keys()) + tuple((json_body or {}).keys()),
                request_payload=payload,
                outbound_bytes=outbound_bytes,
                response_bytes=response_bytes,
                latency_ms=(time.monotonic() - started) * 1000,
                status=response.status_code if response is not None else None,
                result_class="TIMEOUT",
            )
            raise TimeoutError("external provider request timed out") from exc
        except httpx.HTTPError as exc:
            self._record(
                operation=operation,
                fields=tuple((params or {}).keys()) + tuple((json_body or {}).keys()),
                request_payload=payload,
                outbound_bytes=outbound_bytes,
                response_bytes=response_bytes,
                latency_ms=(time.monotonic() - started) * 1000,
                status=response.status_code if response is not None else None,
                result_class="TRANSPORT_ERROR",
            )
            raise ExternalProviderError("external provider transport failed") from exc


class LocalServiceClient(BoundedHttpClient):
    """Private fixed-host transport for an ANIMA-managed service."""

    def __init__(self, *, provider: str, base_url: str, service_host: str, **kwargs: Any) -> None:
        parsed = httpx.URL(base_url)
        if parsed.host != service_host or parsed.path not in {"", "/"}:
            raise ValueError("local provider URL must match its trusted service host")
        super().__init__(
            provider=provider,
            base_url=base_url,
            allowed_hosts=(service_host,),
            require_https=False,
            allow_private=True,
            **kwargs,
        )


def _count(value: Any) -> int:
    return max(1, min(int(value), MAX_RESULT_COUNT))


def _result(provider: str, operation: str, data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return ExternalResult(provider, operation, datetime.now(UTC), data=data, **kwargs).to_payload()


class OpenMeteoProvider:
    def __init__(self, client: BoundedHttpClient) -> None:
        self.client = client

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> dict[str, Any]:
        del timeout
        if name not in {"get", "get_forecast"}:
            raise ExternalProviderError("unknown weather operation")
        latitude = float(arguments["latitude"])
        longitude = float(arguments["longitude"])
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("coordinates are outside WGS84 bounds")
        days = max(1, min(int(arguments.get("forecast_days", 1)), 7))
        fields = "temperature_2m,weather_code,precipitation_probability,wind_speed_10m"
        _, payload = self.client.request(
            operation="weather.get",
            method="GET",
            path="/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "timezone": str(arguments.get("timezone", "UTC")),
                "forecast_days": days,
                "current": fields,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            },
        )
        return _result(
            "open-meteo",
            "weather.get",
            {
                "latitude": latitude,
                "longitude": longitude,
                "timezone": payload.get("timezone"),
                "current": payload.get("current", {}),
                "daily": payload.get("daily", {}),
                "units": payload.get("current_units", {}),
            },
            attribution="Weather data by Open-Meteo.com (CC BY 4.0)",
        )


class SearXNGProvider:
    """Bounded search through the private, operator-configured SearXNG service."""

    def __init__(self, client: BoundedHttpClient) -> None:
        self.client = client

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> dict[str, Any]:
        del timeout
        query = str(arguments["query"]).strip()
        if not query or len(query) > MAX_QUERY_LENGTH:
            raise ValueError("external query is empty or exceeds the 400-character bound")
        if name not in {"search", "search_products"}:
            raise ExternalProviderError("unknown discovery operation")
        operation = "web.search" if name == "search" else "shopping.search_products"
        _, payload = self.client.request(
            operation=operation,
            method="GET",
            path="/search",
            params={
                "q": query,
                "format": "json",
                "categories": "general",
                "pageno": 1,
            },
            headers={"Accept": "application/json"},
        )
        items = payload.get("results", [])
        results = [
            {
                "title": str(item.get("title", "")),
                "url": str(item.get("url", "")),
                "snippet": str(item.get("content", item.get("snippet", ""))),
                "engines": [str(engine) for engine in item.get("engines", []) if engine],
                "rank": index,
            }
            for index, item in enumerate(items[: _count(arguments.get("count", 5))], 1)
            if isinstance(item, dict)
        ]
        return _result(
            "searxng",
            operation,
            {"query": query, "results": results},
            provider_metadata={"configured_engines": ["duckduckgo", "wikipedia"]},
        )


_OVERPASS_TAGS: dict[str, tuple[str, str]] = {
    "restaurant": ("amenity", "restaurant"),
    "cafe": ("amenity", "cafe"),
    "bar": ("amenity", "bar"),
    "grocery": ("shop", "supermarket|convenience"),
    "pharmacy": ("amenity", "pharmacy"),
    "hospital": ("amenity", "hospital"),
    "hardware_store": ("shop", "hardware"),
    "gas_station": ("amenity", "fuel"),
    "hotel": ("tourism", "hotel"),
}


class OverpassProvider:
    """Read-only POI discovery using a fixed Overpass endpoint and tag mapping."""

    def __init__(self, client: BoundedHttpClient) -> None:
        self.client = client

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> dict[str, Any]:
        del timeout
        if name != "search_places":
            raise ExternalProviderError("unknown Overpass operation")
        category = str(arguments["category"])
        if category not in _OVERPASS_TAGS:
            raise ValueError("unsupported place category")
        latitude = float(arguments["latitude"])
        longitude = float(arguments["longitude"])
        radius = max(1, min(int(arguments.get("radius_m", 2_000)), 20_000))
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("coordinates are outside WGS84 bounds")
        key, value = _OVERPASS_TAGS[category]
        tag = f'["{key}"="{value}"]' if "|" not in value else f'["{key}"~"{value}"]'
        query = (
            f"[out:json][timeout:15];(nwr(around:{radius},{latitude},{longitude}){tag};);"
            "out center tags;"
        )
        _, payload = self.client.request(
            operation="places.search",
            method="GET",
            path="/api/interpreter",
            params={"data": query},
            headers={"Accept": "application/json", "User-Agent": "ANIMA-HA/0.1"},
        )
        results: list[dict[str, Any]] = []
        for item in payload.get("elements", [])[: _count(arguments.get("count", 10))]:
            if not isinstance(item, dict):
                continue
            center = item.get("center") or {}
            tags = item.get("tags") or {}
            results.append(
                {
                    "name": str(tags.get("name", "")),
                    "category": category,
                    "address": str(tags.get("addr:street", "")),
                    "coordinates": {
                        "latitude": item.get("lat", center.get("lat")),
                        "longitude": item.get("lon", center.get("lon")),
                    },
                    "provider_reference": f"{item.get('type', '')}/{item.get('id', '')}",
                    "tags": {str(k): str(v) for k, v in tags.items() if k != "name"},
                }
            )
        return _result(
            "openstreetmap-overpass",
            "places.search",
            {"category": category, "results": results},
            attribution="© OpenStreetMap contributors",
        )


class TheMealDBProvider:
    def __init__(self, client: BoundedHttpClient, api_key: str = "1") -> None:
        self.client = client
        self.api_key = api_key

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> dict[str, Any]:
        del timeout
        if name == "search":
            operation, path, params = "recipes.search", "search.php", {"s": arguments["query"]}
        elif name == "get":
            operation, path, params = "recipes.get", "lookup.php", {"i": arguments["recipe_id"]}
        else:
            raise ExternalProviderError("unknown recipe operation")
        _, payload = self.client.request(
            operation=operation,
            method="GET",
            path=f"/api/json/v1/{quote(self.api_key, safe='')}/{path}",
            params=params,
        )
        meals = payload.get("meals") or []
        normalized: list[dict[str, Any]] = []
        for meal in meals[:MAX_RESULT_COUNT]:
            if not isinstance(meal, dict):
                continue
            ingredients = []
            for index in range(1, 21):
                ingredient = str(meal.get(f"strIngredient{index}") or "").strip()
                measure = str(meal.get(f"strMeasure{index}") or "").strip()
                if ingredient:
                    ingredients.append({"ingredient": ingredient, "measure": measure})
            normalized.append(
                {
                    "provider_reference": str(meal.get("idMeal", "")),
                    "name": str(meal.get("strMeal", "")),
                    "category": str(meal.get("strCategory", "")),
                    "cuisine": str(meal.get("strArea", "")),
                    "ingredients": ingredients,
                    "instructions": str(meal.get("strInstructions", ""))[:20_000],
                    "source_url": str(meal.get("strSource", "")),
                }
            )
        return _result(
            "themealdb",
            operation,
            {"query": arguments.get("query"), "recipes": normalized},
            attribution="Recipe data by TheMealDB; prototype/test-key use only",
        )


class NtfyProvider:
    def __init__(self, client: BoundedHttpClient, topic: str, token: str | None = None) -> None:
        if not topic or "/" in topic or len(topic) > 100:
            raise ValueError("configured notification topic is invalid")
        self.client, self.topic, self.token = client, topic, token

    def invoke_with_context(
        self,
        name: str,
        arguments: dict[str, Any],
        timeout: float,
        execution_context: ProviderExecutionContext,
    ) -> dict[str, Any]:
        del timeout
        if name != "send":
            raise ExternalProviderError("unknown notification operation")
        title = str(arguments.get("title", "Anima"))[:120]
        message = str(arguments["message"])[:4_000]
        headers = {"Title": title, "Cache": "no", "Firebase": "no"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self.client.request(
            operation="notifications.send",
            method="POST",
            path=f"/{quote(self.topic, safe='')}",
            json_body={"topic": self.topic, "message": message, "title": title},
            headers=headers,
        )
        return {
            "accepted": True,
            "provider": "ntfy",
            "provider_request_id": hashlib.sha256(
                execution_context.anima_idempotency_key.encode()
            ).hexdigest()[:16],
            "delivery_claim": "provider_accepted_only",
        }

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> dict[str, Any]:
        return self.invoke_with_context(
            name,
            arguments,
            timeout,
            ProviderExecutionContext(UUID(int=0), "standalone"),
        )


def _read_tool(
    name: str, description: str, *, schema: dict[str, Any] | None = None
) -> dict[str, Any]:
    schemas: dict[str, dict[str, Any]] = {
        "get": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number", "minimum": -90, "maximum": 90},
                "longitude": {"type": "number", "minimum": -180, "maximum": 180},
                "timezone": {"type": "string", "maxLength": 64},
                "forecast_days": {"type": "integer", "minimum": 1, "maximum": 7},
                "recipe_id": {"type": "string", "maxLength": 32},
                "query": {"type": "string", "minLength": 1, "maxLength": MAX_QUERY_LENGTH},
            },
            "additionalProperties": False,
        },
        "search": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": MAX_QUERY_LENGTH},
                "count": {"type": "integer", "minimum": 1, "maximum": MAX_RESULT_COUNT},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "search_places": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": sorted(_OVERPASS_TAGS)},
                "count": {"type": "integer", "minimum": 1, "maximum": MAX_RESULT_COUNT},
                "latitude": {"type": "number", "minimum": -90, "maximum": 90},
                "longitude": {"type": "number", "minimum": -180, "maximum": 180},
                "radius_m": {"type": "integer", "minimum": 1, "maximum": 20000},
            },
            "required": ["category", "latitude", "longitude"],
            "additionalProperties": False,
        },
        "search_products": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": MAX_QUERY_LENGTH},
                "count": {"type": "integer", "minimum": 1, "maximum": MAX_RESULT_COUNT},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "list_events": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "maxLength": 64},
                "end": {"type": "string", "maxLength": 64},
                "count": {"type": "integer", "minimum": 1, "maximum": MAX_RESULT_COUNT},
            },
            "additionalProperties": False,
        },
    }
    return {
        "name": name,
        "description": description,
        "input_schema": schema or schemas.get(name, {"type": "object"}),
        "risk_class": "READ_ONLY",
        "semantic_action": name,
        "read_only": True,
        "idempotency": Idempotency.IDEMPOTENT.value,
        "external_content_trust": ExternalContentTrust.EXTERNAL_UNTRUSTED.value,
    }


def external_manifests() -> tuple[PluginManifest, ...]:
    """Return Core-known providers and the first-party local calendar catalogue."""
    from anima_ha.calendar import CALENDAR_MANIFEST

    return (
        PluginManifest(
            plugin_id="anima.external.weather",
            plugin_version="0.1.0",
            manifest_version=1,
            requires_core="0.1.0",
            name="Open-Meteo weather",
            description="Bounded current weather and forecast",
            runtime_kind=RuntimeKind.TRUSTED_NATIVE,
            trust_class=TrustClass.TRUSTED_NATIVE,
            capabilities=("weather",),
            tools=(
                _read_tool(
                    "get",
                    "Get bounded current weather and forecast",
                    schema={
                        "type": "object",
                        "properties": {
                            "latitude": {"type": "number", "minimum": -90, "maximum": 90},
                            "longitude": {"type": "number", "minimum": -180, "maximum": 180},
                            "timezone": {"type": "string", "maxLength": 64},
                            "forecast_days": {"type": "integer", "minimum": 1, "maximum": 7},
                        },
                        "required": ["latitude", "longitude"],
                        "additionalProperties": False,
                    },
                ),
            ),
            source="builtin:anima_ha.external",
        ),
        PluginManifest(
            plugin_id="anima.external.discovery",
            manifest_version=1,
            requires_core="0.1.0",
            plugin_version="0.2.0",
            name="Free local discovery",
            description="Private SearXNG web/product search and OpenStreetMap POI discovery",
            runtime_kind=RuntimeKind.TRUSTED_NATIVE,
            trust_class=TrustClass.TRUSTED_NATIVE,
            capabilities=("web-research", "places", "shopping-research"),
            tools=(
                _read_tool("search", "Search bounded web results"),
                _read_tool("search_places", "Find bounded local places"),
                _read_tool("search_products", "Find bounded product candidates"),
            ),
            network_requirements=("searxng:8080", "overpass-api.de"),
            source="builtin:anima_ha.external",
        ),
        PluginManifest(
            plugin_id="anima.external.recipes",
            plugin_version="0.1.0",
            manifest_version=1,
            requires_core="0.1.0",
            name="TheMealDB recipes",
            description="Bounded recipe search and lookup",
            runtime_kind=RuntimeKind.TRUSTED_NATIVE,
            trust_class=TrustClass.TRUSTED_NATIVE,
            capabilities=("recipes",),
            tools=(
                _read_tool("search", "Search recipes"),
                _read_tool(
                    "get",
                    "Get one recipe",
                    schema={
                        "type": "object",
                        "properties": {"recipe_id": {"type": "string", "maxLength": 32}},
                        "required": ["recipe_id"],
                        "additionalProperties": False,
                    },
                ),
            ),
            source="builtin:anima_ha.external",
        ),
        CALENDAR_MANIFEST,
        PluginManifest(
            plugin_id="anima.external.notifications",
            plugin_version="0.1.0",
            manifest_version=1,
            requires_core="0.1.0",
            name="ntfy notifications",
            description="Bounded provider-accepted notification send",
            runtime_kind=RuntimeKind.TRUSTED_NATIVE,
            trust_class=TrustClass.TRUSTED_NATIVE,
            capabilities=("notifications",),
            tools=(
                {
                    "name": "send",
                    "description": "Send a bounded notification to the configured topic",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "maxLength": 120},
                            "message": {"type": "string", "minLength": 1, "maxLength": 4000},
                        },
                        "required": ["message"],
                        "additionalProperties": False,
                    },
                    "risk_class": "EXTERNAL_SIDE_EFFECT",
                    "semantic_action": "notifications.send",
                    "read_only": False,
                    "idempotency": Idempotency.KEYED.value,
                    "external_content_trust": ExternalContentTrust.EXTERNAL_UNTRUSTED.value,
                    "execution_spec": {"profile": "notifications.send"},
                },
            ),
            required_secrets=("NTFY_TOPIC",),
            network_requirements=("ntfy.sh",),
            source="builtin:anima_ha.external",
        ),
    )


class _DiscoveryProvider:
    """Compose the fixed web and POI providers behind one catalogue plugin."""

    def __init__(self, search: SearXNGProvider, places: OverpassProvider) -> None:
        self.search = search
        self.places = places

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> dict[str, Any]:
        if name == "search_places":
            return self.places.invoke(name, arguments, timeout)
        return self.search.invoke(name, arguments, timeout)


class ExternalNativePlugin:
    """NativeRuntime-compatible wrapper with secret/configuration isolation."""

    def __init__(
        self,
        manifest: PluginManifest,
        factory: Callable[[dict[str, str]], Any],
    ) -> None:
        self.manifest = manifest
        self._factory = factory
        self.provider: Any | None = None

    def start(self, secret_env: dict[str, str]) -> None:
        self.provider = self._factory(dict(secret_env))

    def stop(self) -> None:
        self.provider = None

    def list_tools(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.manifest.tools]

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        if self.provider is None:
            raise ExternalProviderUnavailable("provider is not enabled")
        return self.provider.invoke(name, arguments, timeout)

    def invoke_with_context(
        self,
        name: str,
        arguments: dict[str, Any],
        timeout: float,
        execution_context: ProviderExecutionContext,
    ) -> Any:
        if self.provider is None:
            raise ExternalProviderUnavailable("provider is not enabled")
        method = getattr(self.provider, "invoke_with_context", None)
        if not callable(method):
            return self.provider.invoke(name, arguments, timeout)
        return method(name, arguments, timeout, execution_context)


def external_plugin(
    plugin_id: str,
    *,
    audit_sink: AuditSink | list[ExternalRequestAudit] | None = None,
    transport: httpx.BaseTransport | None = None,
    searxng_url: str = "http://searxng:8080",
    searxng_host: str = "searxng",
    overpass_url: str = "https://overpass-api.de",
) -> tuple[PluginManifest, ExternalNativePlugin]:
    """Build one built-in provider plugin without exposing provider credentials."""
    manifest = next(item for item in external_manifests() if item.plugin_id == plugin_id)

    def client(
        provider: str, base_url: str, hosts: tuple[str, ...], credential: str | None = None
    ) -> BoundedHttpClient:
        return BoundedHttpClient(
            provider=provider,
            base_url=base_url,
            allowed_hosts=hosts,
            audit_sink=audit_sink,
            credential_reference=credential,
            transport=transport,
        )

    if plugin_id == "anima.external.weather":
        return manifest, ExternalNativePlugin(
            manifest,
            lambda env: OpenMeteoProvider(
                client("open-meteo", "https://api.open-meteo.com", ("api.open-meteo.com",))
            ),
        )
    if plugin_id == "anima.external.discovery":
        return manifest, ExternalNativePlugin(
            manifest,
            lambda env: _DiscoveryProvider(
                SearXNGProvider(
                    LocalServiceClient(
                        provider="searxng",
                        base_url=searxng_url,
                        service_host=searxng_host,
                        audit_sink=audit_sink,
                        transport=transport,
                    )
                ),
                OverpassProvider(
                    client(
                        "overpass",
                        overpass_url,
                        (httpx.URL(overpass_url).host or "",),
                    )
                ),
            ),
        )
    if plugin_id == "anima.external.recipes":
        return manifest, ExternalNativePlugin(
            manifest,
            lambda env: TheMealDBProvider(
                client("themealdb", "https://www.themealdb.com", ("www.themealdb.com",))
            ),
        )
    if plugin_id == "anima.external.notifications":
        return manifest, ExternalNativePlugin(
            manifest,
            lambda env: NtfyProvider(
                client(
                    "ntfy",
                    "https://ntfy.sh",
                    ("ntfy.sh",),
                    "NTFY_TOKEN" if "NTFY_TOKEN" in env else None,
                ),
                env["NTFY_TOPIC"],
                env.get("NTFY_TOKEN"),
            ),
        )
    raise ValueError(f"unknown external plugin: {plugin_id}")


def external_resource_gates(secrets: dict[str, str]) -> dict[str, str]:
    """Return explicit availability diagnostics without inspecting secret values."""
    return {
        "EXTERNAL_RESOURCE_GATE_SEARXNG_SEARCH": "CONFIGURED",
        "EXTERNAL_RESOURCE_GATE_OVERPASS": "CONFIGURED",
        "EXTERNAL_RESOURCE_GATE_NTFY": (
            "AVAILABLE" if bool(secrets.get("NTFY_TOPIC")) else "EXTERNAL_RESOURCE_GATE"
        ),
    }
