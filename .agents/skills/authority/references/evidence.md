# Authority Evidence Ladder

- `E0_CLAIMED` — assertion only. Not acceptance evidence.
- `E1_OBSERVED` — directly inspected static fact/source.
- `E2_REPRODUCED` — relevant behavior/problem reproduced sufficiently to establish it exists.
- `E3_TARGET_TESTED` — focused deterministic validation for the target passes.
- `E4_REGRESSION_PROTECTED` — target validation plus relevant broader/pre-existing regression evidence or equivalent independent protection.
- `E5_OPERATIONALLY_OBSERVED` — observed in the authorized real/production-like environment where such validation is appropriate.

Rules:

- Never promote evidence implicitly.
- New target tests alone are at most E3.
- A commit is not runtime evidence.
- An Architect reading a Codex report is not direct live-code observation.
- Use only the minimum level actually achieved, even when the directive requested more.
