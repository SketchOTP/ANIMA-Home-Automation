# Evidence — Best Buy qualification

Date: 2026-09-01

## Starting repository state

- Repository: `/srv/ATLAS/100_ACTIVE/Projects/ANIMA Home Automation`
- Branch: `main`
- Starting SHA: `b5635d07505de2ceba071f984fd7189c8ba18cd9`
- Starting tree: clean; `main == origin/main`
- No implementation files were changed by this directive.
- Governance checkpoint: `7f5ddb0844195e2d558a2fbd24fac3101ae1d34e`
  pushed to `origin/main`; hosted CI `33509082116` passed on that exact SHA.
- Final evidence-closure checkpoint: `dd9dc9b758787d41b5757a1e4119083ecd90db44`
  pushed to `origin/main`; hosted CI `33509236465` passed on that exact SHA.

## Official source matrix

| Source | Observed evidence | Qualification use |
| --- | --- | --- |
| [Best Buy API catalog](https://developer.bestbuy.com/apis) | Products API is presented as an active REST catalog covering current/historical products, pricing, availability, specifications, descriptions, and images. Commerce API is separately identified as invite-only. | Supports API identity and scope separation. |
| [Best Buy API documentation](https://bestbuyapis.github.io/api-documentation/) | API-key registration is described as ordinary email registration and activation; Products API uses `https://api.bestbuy.com/v1/products...`, `search` queries, `show` field selection, and bounded pages. | Supports the candidate transport and model boundary. It does not itself prove zero-cost key issuance. |
| [Best Buy Terms and Conditions](https://developer.bestbuy.com/legal) | Terms require a developer account/key, prohibit key transfer, grant use in software Applications, require attribution and preserved links, require branding where API content appears, prohibit third-party API access, and limit Content storage/cache to temporary use not exceeding 72 hours. Rate limit is 50,000/day and 5/sec for Products and related APIs. | Establishes the material compliance obligations. |

## Persistence conflict

The current AgentRuntime sanitizes external provider results but does not
convert them to metadata-only evidence. `sanitize_tool_result()` retains the
full bounded `result` payload when it fits the 16 KiB result bound. The
PostgreSQL episode store then writes that payload into
`anima_agent_tool_requests.sanitized_result` with no expiry, retention worker,
or purge path. The migration defines the JSONB column but no provider-specific
expiry.

Therefore a Best Buy result containing product names, descriptions, prices,
availability, images, and links could remain in durable episode history beyond
72 hours. This is a direct conflict with the published Best Buy Content
storage/cache rule. The conflict cannot be resolved by a provider wrapper
alone without changing accepted evidence/persistence semantics.

## Cost and key status

- Classification: `UNKNOWN`; no account was created and no payment flow was
  inspected.
- Public documentation describes ordinary email registration and key
  activation, but no public page reviewed here expressly guarantees zero-cost
  issuance or no payment method.
- `BEST_BUY_API_KEY` was not present in the process environment. No secret
  value was printed, inspected, hashed, copied, or committed.
- No Best Buy live request was made; no live product usefulness evidence is
  claimed.

## Decision

`BLOCKED — BEST_BUY_RETENTION_COMPLIANCE` — return to Architect.

Before Best Buy can be integrated, the Architect must authorize a bounded
retention/compliance design that either expires/removes provider Content within
72 hours or preserves only permitted metadata/digests in durable evidence
while keeping current cognition functional. The decision must also confirm the
ordinary key path and future UI attribution/branding obligations.

Walmart is not an active fallback. Its technically qualified implementation and
negative entitlement result remain historical/deferred evidence.

Phase 12 was not implemented.
