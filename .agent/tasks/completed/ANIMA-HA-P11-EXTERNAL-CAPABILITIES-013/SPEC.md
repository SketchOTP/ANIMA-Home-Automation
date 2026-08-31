# Phase 11 bounded specification

Implement bounded external-by-intent capabilities behind ANIMA-owned semantic
adapters. External provider content is data, never authority. Provider access
must use fixed egress, runtime-only credentials, bounded requests/responses,
explicit availability gates, and locally auditable operations.

Adopted surfaces are Open-Meteo weather, Brave web/place/product discovery,
TheMealDB recipes, Google Calendar REST reads/event creation, and configured
ntfy notifications. Calendar creation and notification send remain Phase 9
coordinated external writes. Retailer checkout/cart automation, arbitrary
browser/private endpoint access, UI, voice, compensation, physical-home
claims, and Phase 12 behavior are excluded.

Starting accepted checkpoint: `2c8f88f62c27a728b2bf0861dabaf7a3a3d03e56`.
Phase 10 hosted CI: `33429217008`.
