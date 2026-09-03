# H5V plan

1. Preserve H5U durable approval/action semantics and add an append-only
   continuation record.
2. Reconstruct the original episode context and transcript from the durable
   episode store.
3. Resolve approval or rejection through the existing Phase 9 coordinator,
   append the normalized result, and invoke a second model turn in the same
   episode.
4. Prove approval, rejection, no replay, transcript continuity, and terminal
   Phase 9 status projection with deterministic tests and real OPA evidence.
5. Run applicable regressions, inspect the final diff, and update governance
   records without self-accepting Phase 12.
