# Evidence — Walmart entitlement qualification

Date: 2026-09-01

## Verdict

`BLOCKED — WALMART_CLARIFICATION_REQUIRED`

Architect disposition: `INVESTIGATE — PROVIDER ENTITLEMENT QUALIFICATION`.
This is not a provider rejection and not Phase 11 acceptance. The existing
provider remains a candidate pending entitlement clarification.

## Starting state

- Repository: `main`, clean and tracking `origin/main`.
- Starting SHA: `a1122b32d1e9d6548b5c78bd1256185d60b4d281`.
- Exact hosted CI for the technical checkpoint: `33501648332`, success.
- No implementation files changed during this investigation.

## Source matrix

| Source | Date/status | Evidence and limit |
|---|---|---|
| [Walmart Affiliates FAQ](https://affiliates.walmart.com/faqs) | Current page checked 2026-09-01 | Says joining is free, acceptance is required, and affiliate links/data feeds are supplied through the Affiliate Member Center. Does not establish ANIMA coverage. |
| [Walmart Affiliates Operating Agreement](https://affiliates.walmart.com/terms) | Current page checked 2026-09-01; page identifies April 2026 update | Requires accepted enrollment; Walmart may approve each Affiliate Website; Qualifying Links must be Walmart/Platform-provided and direct to Walmart; clear/conspicuous advertising disclosure is required; current product price/availability must be maintained within 24 hours of updates; rights are limited, non-transferable, and revocable for Program purposes. Does not resolve private-local-assistant use or the exact legacy API terms. |
| [Walmart developer API License Agreement](https://developer.walmart.com/global-marketplace/docs/terms-and-conditions) | Current page checked 2026-09-01 | Contextual only, not proof of governance for the affiliate endpoint. It states Approved Purposes, non-transferability/non-sublicensability, key protection, possible account-specific call limits/fees, and restrictions on disclosure/distribution/reuse. |
| Walmart developer documentation search | Checked 2026-09-01 | Current public pages found primarily document Marketplace APIs and do not re-establish the exact `affil/product/v2` affiliate entitlement or its account-specific scope. |
| LedgerMind source/runbook | Read-only Atlas inspection 2026-09-01 | Documents Walmart.io affiliate APIs, the signed `developer.api.walmart.com/api-proxy/service/affil/product/v2` family, stage/production application key setup, and optional Impact publisher ID. This establishes project history and technical identity, not permission for ANIMA. |
| LedgerMind smoke evidence | Prior sanitized status-only evidence | Signature/catalogue/search/store/price probes passed; cart push unsupported. Technical operation is not contractual authorization. |
| Walmart/Impact dashboard | Not available in an already-authorized Codex session | Application name/type, environment approval, approved surface/domain, and publisher metadata could not be inspected. No login or account mutation was attempted. |

## Exact API/program identity

The strongest available identity is the Walmart.io Affiliate Product API v2
contract documented by LedgerMind, using RSA-signed headers and the fixed
`https://developer.api.walmart.com/api-proxy/service/affil/product/v2` family.
The exact public current support classification is `UNKNOWN`: the endpoint
responds in the existing operator environment, but current official Walmart
developer pages reviewed here do not publish a current page establishing that
legacy affiliate path's support status, replacement path, or account-specific
terms. HTTP success is not treated as authorization.

## Entitlement conclusions

| Question | Result | Basis |
|---|---|---|
| Affiliate program cost | `ZERO_COST_TO_JOIN` | Official FAQ says the program is free to join. |
| Specific API/application incremental cost | `UNKNOWN` | No account pricing exhibit was available; current API-license material allows fees if communicated. |
| Existing LedgerMind entitlement active | `TECHNICALLY_OBSERVED`, contract status unknown | Read-only docs plus prior sanitized smoke evidence; no dashboard metadata. |
| Cross-project reuse by ANIMA HA | `UNCLEAR_REQUIRES_APPROVAL` | LedgerMind records do not establish ANIMA as an approved application/surface; current rights are limited/non-transferable in the reviewed API terms. |
| Private local-assistant use | `UNCLEAR_REQUIRES_CLARIFICATION` | Affiliate terms are written around approved Affiliate Websites and Qualifying Links; they do not clearly cover a private household assistant. |
| Signed API automation | `TECHNICALLY_SUPPORTED`, entitlement scope unresolved | LedgerMind uses the signed API path; authorization of this application's use is unproven. |
| Product-data display/persistence | `UNCLEAR_REQUIRES_CLARIFICATION` | Terms establish limited Program-purpose rights and restrictions, but exact API data/cache rights for this surface are not published in the reviewed sources. |
| Price/availability | `24_HOUR_UPDATE_OBLIGATION_WHERE_TERMS_APPLY` | Affiliate terms require updates within 24 hours of an update and require the Walmart-site price to govern when different. ANIMA must not claim broader permission. |
| Product URLs | `QUALIFYING_LINK_RULE_UNRESOLVED_FOR_ANIMA` | Ordinary `walmart.com/ip/<item>` URLs are not proven to be Qualifying Links; terms say only Walmart/Platform-provided qualifying links may be used and direct to Walmart. |
| Publisher ID | `UNKNOWN_IF_MANDATORY` | LedgerMind documents it as optional for existing probes; no current account/API rule was found establishing whether ANIMA display/use requires it. |
| Disclosure | `REQUIRED_FOR_QUALIFYING_LINK_DISPLAY_WHERE_TERMS_APPLY` | Clear/conspicuous advertising disclosure is required; endorsements with qualifying links are identified in the terms as `#WalmartPartner` or `paid link`. Exact local-assistant treatment remains unresolved. |
| Rate limits | `UNKNOWN` | Current exact affiliate-path limit was not published in the reviewed official material. |
| Support/deprecation/replacement | `UNKNOWN` | Exact current official support/migration statement for `affil/product/v2` was not found. |
| AI/agent use | `UNCLEAR_REQUIRES_CLARIFICATION` | No explicit current permission for ANIMA-style automated/LLM product research was found; no inference from silence. |

## Required operator action

In an already-authorized Walmart.io/Impact session, inspect only nonsecret
metadata: application name/type, stage/production status, approved
website/application surface, Affiliate/Impact membership, and product API
entitlement. Do not expose IDs, keys, tokens, or private-key material.

If that metadata does not explicitly cover ANIMA, ask Walmart Affiliate/API
support this single narrow question:

> Does our existing Walmart.io Affiliate Product API v2 application and account authorize signed read-only product research from a private, household-local ANIMA HA application separate from LedgerMind, including displaying product data/prices and Walmart links; if so, what exact approved surface, qualifying-link/publisher-ID format, disclosure, freshness/cache, and data-retention rules apply?

No application registration, agreement acceptance, support submission, or
account change was performed by Codex.

## Safety and scope evidence

- No secret values, consumer IDs, publisher identifiers, tokens, private-key
  contents, `.env` contents, runtime household data, or credential payloads
  were inspected, copied, hashed, committed, or transmitted.
- LedgerMind was inspected read-only; its dirty working tree was preserved.
- ANIMA implementation files were not modified.
- No alternate provider, disclosure/UI, cart, checkout, or Phase 12 behavior
  was implemented.
