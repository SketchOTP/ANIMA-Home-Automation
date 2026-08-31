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
    ) -> None:
        parsed = httpx.URL(base_url)
        if parsed.scheme != "https" or parsed.host is None:
            raise ValueError("external providers require an HTTPS base URL")
        if parsed.host not in allowed_hosts or not self._safe_host(parsed.host):
            raise ValueError("base URL host is not allowlisted")
        self.provider = provider
        self.base_url = str(parsed).rstrip("/")
        self.allowed_hosts = frozenset(allowed_hosts)
        self.audit_sink = audit_sink
        self.credential_reference = credential_reference
        self.max_response_bytes = max_response_bytes
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
        if url.host not in self.allowed_hosts or not self._safe_host(url.host):
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


class BraveProvider:
    def __init__(self, client: BoundedHttpClient, api_key: str) -> None:
        if not api_key.strip():
            raise ExternalProviderUnavailable("BRAVE_SEARCH_API_KEY is missing")
        self.client = client
        self.api_key = api_key

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> dict[str, Any]:
        del timeout
        query = str(arguments["query"]).strip()
        if not query or len(query) > MAX_QUERY_LENGTH:
            raise ValueError("external query is empty or exceeds the 400-character bound")
        if name == "search" or name == "search_products":
            operation = "web.search" if name == "search" else "shopping.search_products"
            _, payload = self.client.request(
                operation=operation,
                method="GET",
                path="/res/v1/web/search",
                params={"q": query, "count": _count(arguments.get("count", 5)), "country": "US"},
                headers={"X-Subscription-Token": self.api_key, "Accept": "application/json"},
            )
            items = payload.get("web", {}).get("results", [])
            results = [
                {
                    "title": str(item.get("title", "")),
                    "url": str(item.get("url", "")),
                    "snippet": str(item.get("description", "")),
                    "rank": index,
                }
                for index, item in enumerate(items[:MAX_RESULT_COUNT], 1)
                if isinstance(item, dict)
            ]
            return _result("brave", operation, {"query": query, "results": results})
        if name == "search_places":
            params: dict[str, Any] = {
                "q": query,
                "count": _count(arguments.get("count", 5)),
            }
            for key in ("latitude", "longitude", "radius"):
                if key in arguments:
                    params[key] = arguments[key]
            _, payload = self.client.request(
                operation="places.search",
                method="GET",
                path="/res/v1/local/place_search",
                params=params,
                headers={"X-Subscription-Token": self.api_key, "Accept": "application/json"},
            )
            places = payload.get("results", [])
            results = [
                {
                    "name": str(item.get("name", "")),
                    "category": str(item.get("type", "")),
                    "address": str(item.get("address", "")),
                    "coordinates": item.get("coordinates"),
                    "provider_reference": str(item.get("id", "")),
                }
                for item in places[:MAX_RESULT_COUNT]
                if isinstance(item, dict)
            ]
            return _result("brave", "places.search", {"query": query, "results": results})
        raise ExternalProviderError("unknown discovery operation")


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


class GoogleCalendarProvider:
    def __init__(
        self, client: BoundedHttpClient, access_token: str, calendar_id: str = "primary"
    ) -> None:
        if not access_token.strip():
            raise ExternalProviderUnavailable("Google Calendar credential is missing")
        self.client, self.access_token, self.calendar_id = client, access_token, calendar_id

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}

    @staticmethod
    def _event(value: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider_reference": str(value.get("id", "")),
            "title": str(value.get("summary", "")),
            "start": str(
                value.get("start", {}).get("dateTime", value.get("start", {}).get("date", ""))
            ),
            "end": str(value.get("end", {}).get("dateTime", value.get("end", {}).get("date", ""))),
            "location": str(value.get("location", "")),
            "status": str(value.get("status", "")),
            "updated": str(value.get("updated", "")),
        }

    def invoke_with_context(
        self,
        name: str,
        arguments: dict[str, Any],
        timeout: float,
        execution_context: ProviderExecutionContext,
    ) -> dict[str, Any]:
        del timeout
        base = f"/calendar/v3/calendars/{quote(self.calendar_id, safe='')}/events"
        if name == "list_events":
            _, payload = self.client.request(
                operation="calendar.list_events",
                method="GET",
                path=base,
                params={
                    "timeMin": arguments.get("start"),
                    "timeMax": arguments.get("end"),
                    "maxResults": _count(arguments.get("count", 10)),
                    "singleEvents": "true",
                },
                headers=self._headers(),
            )
            return _result(
                "google-calendar",
                "calendar.list_events",
                {
                    "events": [
                        self._event(item)
                        for item in payload.get("items", [])
                        if isinstance(item, dict)
                    ]
                },
            )
        if name != "create_event":
            raise ExternalProviderError("unknown calendar operation")
        provider_id = hashlib.sha256(execution_context.anima_idempotency_key.encode()).hexdigest()[
            :32
        ]
        event = {
            "id": provider_id,
            "summary": str(arguments["summary"]),
            "start": {"dateTime": str(arguments["start"])},
            "end": {"dateTime": str(arguments["end"])},
        }
        try:
            _, existing = self.client.request(
                operation="calendar.create_event.precheck",
                method="GET",
                path=f"{base}/{provider_id}",
                headers=self._headers(),
            )
            readback = self._event(existing)
            return {
                "accepted": True,
                "already_satisfied": True,
                "readback_verified": self._matches(readback, arguments),
                "readback": readback,
            }
        except ExternalProviderError as exc:
            if "HTTP 404" not in str(exc):
                raise
        _, created = self.client.request(
            operation="calendar.create_event",
            method="POST",
            path=base,
            params={"conferenceDataVersion": 0},
            json_body=event,
            headers={**self._headers(), "Content-Type": "application/json"},
        )
        try:
            _, observed = self.client.request(
                operation="calendar.create_event.readback",
                method="GET",
                path=f"{base}/{provider_id}",
                headers=self._headers(),
            )
        except (ExternalProviderError, TimeoutError):
            return {"accepted": True, "readback_verified": False, "provider_ack": created}
        readback = self._event(observed)
        return {
            "accepted": True,
            "readback_verified": self._matches(readback, arguments),
            "readback": readback,
            "provider_ack": {"provider_reference": str(created.get("id", provider_id))},
        }

    @staticmethod
    def _matches(readback: dict[str, Any], arguments: dict[str, Any]) -> bool:
        return (
            readback.get("title") == str(arguments["summary"])
            and readback.get("start") == str(arguments["start"])
            and readback.get("end") == str(arguments["end"])
        )

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
                "query": {"type": "string", "minLength": 1, "maxLength": MAX_QUERY_LENGTH},
                "count": {"type": "integer", "minimum": 1, "maximum": MAX_RESULT_COUNT},
                "latitude": {"type": "number", "minimum": -90, "maximum": 90},
                "longitude": {"type": "number", "minimum": -180, "maximum": 180},
                "radius": {"type": "integer", "minimum": 1, "maximum": 50000},
            },
            "required": ["query"],
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
    """Return the Core-known external manifests; credentials are independently gated."""
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
            plugin_version="0.1.0",
            manifest_version=1,
            requires_core="0.1.0",
            name="Brave discovery",
            description="Bounded web, place, and product discovery",
            runtime_kind=RuntimeKind.TRUSTED_NATIVE,
            trust_class=TrustClass.TRUSTED_NATIVE,
            capabilities=("web-research", "places", "shopping-research"),
            tools=(
                _read_tool("search", "Search bounded web results"),
                _read_tool("search_places", "Find bounded local places"),
                _read_tool("search_products", "Find bounded product candidates"),
            ),
            required_secrets=("BRAVE_SEARCH_API_KEY",),
            network_requirements=("api.search.brave.com",),
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
        PluginManifest(
            plugin_id="anima.external.calendar",
            plugin_version="0.1.0",
            manifest_version=1,
            requires_core="0.1.0",
            name="Google Calendar",
            description="Bounded Calendar reads and verified event creation",
            runtime_kind=RuntimeKind.TRUSTED_NATIVE,
            trust_class=TrustClass.TRUSTED_NATIVE,
            capabilities=("calendar",),
            tools=(
                _read_tool("list_events", "List bounded calendar events"),
                {
                    "name": "create_event",
                    "description": "Create a calendar event with provider readback",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string", "minLength": 1, "maxLength": 200},
                            "start": {"type": "string", "maxLength": 64},
                            "end": {"type": "string", "maxLength": 64},
                        },
                        "required": ["summary", "start", "end"],
                        "additionalProperties": False,
                    },
                    "risk_class": "EXTERNAL_SIDE_EFFECT",
                    "semantic_action": "calendar.create_event",
                    "read_only": False,
                    "idempotency": Idempotency.KEYED.value,
                    "external_content_trust": ExternalContentTrust.EXTERNAL_UNTRUSTED.value,
                    "execution_spec": {"profile": "calendar.create_event"},
                },
            ),
            required_secrets=("GOOGLE_CALENDAR_ACCESS_TOKEN",),
            network_requirements=("www.googleapis.com",),
            source="builtin:anima_ha.external",
        ),
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
    calendar_id: str = "primary",
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
            lambda env: BraveProvider(
                client(
                    "brave",
                    "https://api.search.brave.com",
                    ("api.search.brave.com",),
                    "BRAVE_SEARCH_API_KEY",
                ),
                env["BRAVE_SEARCH_API_KEY"],
            ),
        )
    if plugin_id == "anima.external.recipes":
        return manifest, ExternalNativePlugin(
            manifest,
            lambda env: TheMealDBProvider(
                client("themealdb", "https://www.themealdb.com", ("www.themealdb.com",))
            ),
        )
    if plugin_id == "anima.external.calendar":
        return manifest, ExternalNativePlugin(
            manifest,
            lambda env: GoogleCalendarProvider(
                client(
                    "google-calendar",
                    "https://www.googleapis.com",
                    ("www.googleapis.com",),
                    "GOOGLE_CALENDAR_ACCESS_TOKEN",
                ),
                env["GOOGLE_CALENDAR_ACCESS_TOKEN"],
                calendar_id,
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
        gate: "AVAILABLE" if name in secrets and bool(secrets[name]) else "EXTERNAL_RESOURCE_GATE"
        for gate, name in {
            "EXTERNAL_RESOURCE_GATE_BRAVE_SEARCH": "BRAVE_SEARCH_API_KEY",
            "EXTERNAL_RESOURCE_GATE_GOOGLE_CALENDAR": "GOOGLE_CALENDAR_ACCESS_TOKEN",
            "EXTERNAL_RESOURCE_GATE_NTFY": "NTFY_TOPIC",
        }.items()
    }
