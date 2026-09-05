# Plan

1. Reconstruct accepted Phase 13 state and inspect existing lifecycle, action,
   task, calendar, HA, plugin, journal, SENTRY, backup, and validation seams.
   Do not alter the protected SENTRY V0.4 tree.
2. Add one canonical scenario dataclass, bounded test-only fault injector, and
   deterministic replay comparator. Keep faults unreachable from browser, MCP,
   model input, and ordinary production configuration.
3. Extend focused tests across provider ambiguity, fencing, action/approval,
   event ordering, outages, restricted content, and SENTRY outage behavior.
4. Add a bounded Phase 14 verifier that emits a secret-free JSON scenario
   ledger, using real ANIMA stores and policy/action boundaries where available.
5. Exercise PostgreSQL dump/restore in an isolated environment when available;
   re-observe HA state after restore and prove no side-effect replay.
6. Exercise historical replay and regression detection against the canonical
   ledger. Report unavailable infrastructure as an explicit gate.
7. Run complete validation/build/safety checks, update governance records, commit,
   push, and validate exact-head CI.

No Phase 15 household demonstration or new household capability is in scope.
