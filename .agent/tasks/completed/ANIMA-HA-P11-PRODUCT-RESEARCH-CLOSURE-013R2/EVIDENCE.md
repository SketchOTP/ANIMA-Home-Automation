# Phase 11 product-research evidence

## Provider decision

- Existing LedgerMind source was inspected read-only on the Atlas laptop at
  `/home/sketch/Projects/LedgerMind`.
- Its status-only Walmart smoke test passed signature, catalogue, stores,
  keyword search, ZIP-scoped pricing, and store-scoped pricing probes. Cart
  push/checkout remained unsupported.
- ANIMA wraps the signed Walmart.io affiliate Product API v2 path. No
  credential value, private key, `.env`, or runtime data was copied into this
  repository.
- Private SearXNG remains the general web provider. eBay HTML extraction,
  arbitrary retailer scraping, CAPTCHA bypass, browser automation, and
  speculative provider replacement remain rejected.

## Implementation

- `WalmartProductProvider` signs bounded GET `/search` requests to the fixed
  `developer.api.walmart.com` host using operator-provided references resolved
  at runtime through the trusted secret boundary.
- `ProductCandidate` data is kept distinct from a nested `retail_offer`.
  Prices and availability are timestamped external observations, not Truth.
- The manifest exposes only `query` and bounded `count` to the model. The
  provider host, credentials, signature, and cart/checkout decisions are
  system-owned.
- Actual AgentRuntime integration proves the shared catalogue selects the
  Walmart semantic tool and carries the normalized result as
  `EXTERNAL_UNTRUSTED`.

## Live usefulness evidence

Credentialed Atlas validation mapped LedgerMind's operator environment into
ANIMA's trusted secret boundary without printing secrets:

| Query | Distinct Walmart candidates | Result |
| --- | ---: | --- |
| `wireless headphones` | 9 | PASS |
| `air fryer` | 10 | PASS |

Both queries exceed the three-candidate usefulness threshold and preserve
provider references/source URLs. Evidence class: `LIVE_CREDENTIALED`, Atlas
x86-64. This does not claim purchase, checkout, physical-home, production-
scale, or native ARM64 behavior.

## Validation

- `uv sync --locked --dev`: PASS.
- Ruff format/check: PASS.
- strict mypy: PASS (`42` source files).
- Full pytest: PASS (`139 passed`).
- OPA: PASS (`4/4`).
- sdist/wheel build: PASS.
- `git diff --check`: PASS.
- Public-safety scan: PASS; no secrets or private runtime artifacts added.
- Local no-credential harness reports the Walmart resource gate explicitly.
- Credentialed Atlas harness with `--require-walmart-products` passed both live
  queries and reported `EXTERNAL_RESOURCE_GATE_WALMART_PRODUCT_SEARCH=AVAILABLE`.

## Limitations

- The operator's existing Walmart entitlement cost/terms were not
  independently requalified in this bounded continuation. The implementation
  does not make a universal zero-cost claim; absent or unreadable settings
  remain `EXTERNAL_RESOURCE_GATE_WALMART_PRODUCT_SEARCH`.
- Current public Walmart developer documentation primarily describes
  Marketplace OAuth APIs, so the inspected LedgerMind affiliate path is
  supported here by source inspection plus live smoke evidence, not by
  conflating those API families.
- No cart, checkout, payment, human purchase, physical-home, production-scale,
  or Phase 12 behavior was implemented.

## Publication

- Implementation checkpoint: `fb0a6a02c9a48aaa7254e1eb69ec77c1fcd8469a`.
- Implementation hosted CI: `33501513385`, success on the exact SHA.
- Final governed checkpoint: to be filled after the governance commit.
- Final governed hosted CI: to be filled after the exact-SHA run.
