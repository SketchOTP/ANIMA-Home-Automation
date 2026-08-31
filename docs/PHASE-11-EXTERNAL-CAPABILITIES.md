# Phase 11 — External-by-Intent Capability Plugins

Phase 11 adds bounded external capabilities behind ANIMA-owned semantic
adapters. Provider APIs do not cross into Core, external content is
`EXTERNAL_UNTRUSTED`, and every egress operation is locally auditable without
recording credentials or raw authorization headers.

## Architecture

```text
Luna / scripted cognition
  -> bounded semantic tool schema
  -> Phase 5 Tool Gateway + Phase 4 policy
  -> built-in provider adapter
  -> fixed-host BoundedHttpClient
  -> normalized ExternalResult / provider evidence
```

Reads remain `READ_ONLY`. Calendar creation and notification send are exact
Core-owned `COORDINATED_CONSEQUENTIAL` profiles and enter the existing Phase 9
coordinator. The profiles define expected effects before dispatch:

* Calendar: deterministic provider event identity, provider GET precheck,
  POST, then provider GET readback. Success means normalized readback matches;
  an acknowledgement alone is not success.
* ntfy: provider receipt means only that the provider accepted one request. It
  does not mean a person received or read it. Ambiguous sends are not retried.

Arbitrary plugins cannot select hosts, headers, credentials, topics, or Phase 9
evidence authority. The fixed allowlist and the exact Core profile mapping are
implemented in `src/anima_ha/external.py` and `src/anima_ha/action.py`.

## Provider and dependency decisions

| Capability | Provider / dependency | Disposition | Boundary and limitation |
| --- | --- | --- | --- |
| Weather | Open-Meteo Forecast API | ADOPT / WRAP | No-key prototype endpoint; coordinates and requested fields only; CC BY 4.0 attribution; free endpoint is non-commercial and rate-limited. |
| Web / places / products | Brave Search API | ADOPT / WRAP, credential-gated | `BRAVE_SEARCH_API_KEY` is brokered outside model input; bounded web and place endpoints; query length and count bounded; provider retention/privacy must be reviewed before deployment. |
| Recipes | TheMealDB V1 API | ADOPT / WRAP for prototype | Official API/test key `1` is suitable for development; public appstore/production use requires supporter arrangements. |
| Calendar | Google Calendar REST API | ADOPT / WRAP, credential-gated | Direct REST is foundational; access token is runtime-only; narrow event scopes; deterministic event ID and readback. |
| Calendar MCP | Google Workspace Calendar MCP | REFERENCE / DEFER | Official but Developer Preview; unnecessary MCP/OAuth lifecycle coupling while direct REST satisfies the bounded prototype. |
| Notifications | ntfy HTTP publish API | ADOPT / WRAP | Configured host/topic/token only; synthetic public evidence uses random topic, `Cache: no`, and `Firebase: no`; provider acceptance is not human delivery. |
| HTTP | `httpx==0.28.1` | ADOPT / WRAP | Stable line; fixed base URL, TLS, no redirects, bounded timeout/body, explicit methods, and audit. |
| Google auth | `google-auth==2.57.0`, `google-auth-oauthlib==1.4.1` | ADOPT for Calendar commissioning path | Runtime credentials remain outside model, journal, and repository; native ARM64 execution is not yet qualified. |
| Retailer cart / checkout | None | DEFER | No stable, defensible public consumer cart API was adopted; browser automation, private endpoints, cookie reuse, and checkout/payment are prohibited. |

## Normalized result and egress audit

`ExternalResult` contains provider, semantic operation, retrieval time,
freshness, explicit `EXTERNAL_UNTRUSTED` trust, attribution, source records,
bounded structured data, and provider metadata. Search/place/product results
retain source URL/provider references; place IDs remain external references and
never become Household Graph IDs. Product price, stock, rating, shipping, and
variant fields are absent unless returned by the provider.

`ExternalRequestAudit` records provider, operation, timestamp, request field
names, request digest, byte counts, latency, status, result class, and a
credential reference name. It never records API-key/token values, OAuth
refresh material, ntfy topics/tokens, or authorization headers.

The adapter receives only explicit semantic arguments. No ContextPacket,
household memory, graph, camera history, or identity evidence is passed to a
provider. Arbitrary URLs, private/loopback IPs, file URLs, redirects, methods,
headers, and provider query parameters are not model tools.

## Credential gates and live evidence

Provider availability is independent. Missing Brave or Google credentials are
reported as `EXTERNAL_RESOURCE_GATE_BRAVE_SEARCH` or
`EXTERNAL_RESOURCE_GATE_GOOGLE_CALENDAR`; they do not disable weather, recipes,
or other providers. The live harness performs synthetic Open-Meteo and
TheMealDB reads and one synthetic ntfy send when reachable. Brave and Google
are live only when their ANIMA-owned credentials are configured; otherwise
contract tests are the highest evidence and no live claim is made.

## Trust and failure behavior

Provider text remains data even when it contains instructions such as
`IGNORE YOUR SYSTEM INSTRUCTIONS`; it cannot change the tool catalogue,
policy, permissions, or egress. Provider outage is normalized as an explicit
failure and does not mutate policy or other plugin health. Reads may be bounded
and retried only where a future adapter explicitly qualifies safe retry.
External writes are never blindly retried after possible dispatch.

## Evidence boundary

The Phase 11 evidence is local x86-64, Python 3.12, and synthetic public
provider traffic. It is not native Raspberry Pi/ARM64 qualification, a
physical-home test, production commercial-provider approval, production
capacity evidence, or a claim that a notification reached a human. Phase 12
custom interface and later behavior are not implemented.
