# Specification

- Browser talks only to the ANIMA-owned `/api/v1` semantic API and static same-origin assets.
- Home Assistant OAuth is a bootstrap identity proof; ANIMA maps the returned HA user ID through an exact configured household/principal map.
- Cookies are HttpOnly and SameSite Strict. Session and CSRF secrets are stored as digests; mutation requests require an exact same-origin `Origin` and CSRF header.
- Read endpoints expose semantic home, task, calendar, activity, capability, and bootstrap models. Raw rows, provider payloads, policy internals, credentials, and arbitrary tools are excluded.
- Commands are routed through an injected Core gateway. The default production gateway is unavailable/fail-closed; no UI route directly mutates a database or provider.
- Conversation ingress journals a normalized `user.request` envelope and may invoke only an injected journal/attention/context/AgentRuntime bridge. Deterministic echo is test-only.
- SSE contains only bounded invalidation names; clients refetch models.
- The UI has no localStorage, IndexedDB, service worker, or external asset/network dependency.
