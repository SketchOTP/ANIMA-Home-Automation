# H5T evidence

## Result

`PARTIAL / CONTINUE — SAME-BROWSER SESSION AND POST-RESTART REFETCH OBSERVED; DUPLICATE-MUTATION PROOF NOT ESTABLISHED`.

Retrieval confidence is `ADEQUATE`. The exact candidate runtime was started
with server process PID `1073682`; the prior candidate process was PID
`1059121`. The same browser tab was retained while the candidate process was
stopped and restarted. No new login or browser context was used.

## Validation

- `PASSED / E3_TARGET_TESTED` — before restart, the browser reached the
  authenticated household UI and the H5R surfaces were visible.
- `PASSED / E3_TARGET_TESTED` — after the real process restart, the same tab
  reloaded to the authenticated household UI without returning to login;
  Rooms & devices, System health, and the configured H5R surface remained
  visible.
- `PASSED / E3_TARGET_TESTED` — PostgreSQL-backed presentation state remained
  visible after restart: appearance `light`, display mode `phone`, and the
  configured widget set/order were preserved. Server logs showed post-restart
  bootstrap, home, settings, and events refetches.
- `NOT RUN` — browser cookie/storage inspection was intentionally not
  performed; continuity is established by visible same-tab behavior and
  server/session evidence only.
- `NOT RUN` — a successful bounded mutation followed by restart and exact
  no-duplicate accounting. The attempted task test produced UI status
  `FAILED / ValueError` and no matching durable task row; it is retained as
  negative evidence rather than a mutation pass.
- `PASSED` — candidate process was stopped after evidence capture; the
  pre-existing port-18090 service was not modified.

## Evidence boundary and remaining gap

Same-browser post-restart continuity/refetch evidence is `E3_TARGET_TESTED`.
The stronger no-duplicate mutation claim is unproven, so this directive cannot
close the complete restart/recovery gate. H5 browser-only denial, provider
recovery, restricted reload/storage, isolated-HA UI, calendar fixture, and
confirmation continuation gaps remain outside this directive and unclaimed.
