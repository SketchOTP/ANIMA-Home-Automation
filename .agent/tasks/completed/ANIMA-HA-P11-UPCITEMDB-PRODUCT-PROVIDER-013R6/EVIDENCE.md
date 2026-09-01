# Evidence

## Starting state

- Starting governed SHA: `5ddf1eceb1346377d1ab3f857f1cadb9eeb3cf61`.
- Branch: `main`; starting tree was clean and matched `origin/main`.
- No provider credentials, accounts, or secret values were used.
- Implementation SHA: `2031f0a9ebded7e7a444516ab619f685d519349f`.
- Implementation hosted CI: `33562526807`, success on the exact implementation SHA.

## External qualification

- Endpoint: `https://api.upcitemdb.com/prod/trial/search`.
- Authentication: no signup and no API key.
- Live `wireless headphones`: HTTP 200, 5 distinct EAN identifiers, 13
  bounded offers, response `X-RateLimit-Limit=100`, remaining `93`.
- Live `air fryer`: HTTP 200, 5 distinct EAN identifiers, 19 bounded offers,
  response `X-RateLimit-Limit=100`, remaining `92`.
- The API's plan and rate-limit pages disagree on free search quota. ANIMA
  adopts the stricter 20-search/day interpretation, 15-second local pacing,
  and header/`Retry-After` compliance.
- Several live offer timestamps are old. Prices and availability therefore
  remain timestamped external observations; historical price ranges are not
  current offers.

## Implementation

- `UPCItemDBProductProvider` uses fixed `api.upcitemdb.com` HTTPS and only the
  bounded `/prod/trial/search` path.
- The semantic model-facing tool remains `shopping.search_products` with only
  `query` and `count` inputs. No credential or host input is model-visible.
- Normalization preserves EAN/UPC/GTIN identity, brand/model/category,
  bounded description/specifications, provider source URL, bounded offers,
  provider-returned offer links, offer timestamps, and separate historical
  price ranges.
- Core maps the UPCitemdb tool to `EPHEMERAL_RESTRICTED`. The existing taint
  boundary blocks later tools and removes full provider content from durable
  episode/turn/tool/export storage.

## Tests and live harness

- Deterministic provider normalization and fixed-host tests passed.
- Rate-limit pacing and `Retry-After` no-retry tests passed.
- Actual AgentRuntime broad-catalogue UPCitemdb path passed.
- Restricted-content PostgreSQL/export sentinel scan passed with UPCitemdb
  sentinels: zero database hits and zero in-process export occurrences.
- `scripts/verify_phase11_external.py --require-upcitemdb-products` passed the
  two strict live product targets. Open-Meteo, TheMealDB, Overpass, and local
  calendar checks also passed; private SearXNG was unavailable in this run and
  reported its resource gate honestly.

## Terms and limits

Official UPCitemdb terms grant a limited, terminable service-use license,
disclaim accuracy/availability, and place third-party-rights responsibility on
the customer. The API documentation states that Amazon/eBay affiliate sales
information shown on the website is not redistributed through the API. ANIMA
does not infer omitted offers and keeps provider content restricted/untrusted.

## Evidence limitations

- Live evidence is public synthetic x86-64 traffic, not production scale or
  native ARM64/Pi execution.
- Product usefulness is established for the two required queries, but the
  provider's own stale offer timestamps mean current retail freshness is not
  established.
- The repository-wide Ruff scan still has the known unrelated pre-existing
  failures in `scripts/verify_phase5_plugins.py`; changed-scope Ruff and
  hosted CI validation are clean.
- `pg_dump` is unavailable; the restricted export check uses an in-process
  complete JSON export over all public `anima_*` tables.
- Phase 12 was not implemented.
