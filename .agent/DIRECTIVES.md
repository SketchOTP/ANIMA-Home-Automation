# Directive Ledger

Append new directives at the bottom; never rewrite an accepted historical directive.

---

## AUTHORITY-BOOTSTRAP-001 — Install Authority 3.0 for ANIMA HA

- Issued: 2026-08-28
- Status: COMPLETE
- Project stage: BOOTSTRAP
- Goal link: Establishes the governance, state, evidence, and handoff structures required to build and independently verify the adopted ANIMA HA prototype goal.
- Objective: Install the Authority 3.0 package, populate project-specific state records, and preserve the adopted `PROJECT_GOAL.md` contract.
- Scope: Root `AGENTS.md`, `.agent/` project state/history structure, `.agents/` reusable Authority workflow, and project-specific Architect startup prompt.
- Exclusions: No implementation, dependency adoption, GitHub creation, deployment, production work, or weakening/narrowing of the adopted goal.
- Acceptance: Required Authority files exist; project identity and Notion SSOT are recorded; `PROJECT_GOAL.md` contains the authorized adopted goal; empty implementation state is represented honestly; append-only bootstrap evidence is recorded.
- Required validation: File inventory and content inspection; no implementation acceptance implied. Minimum evidence `E2_REPRODUCED` for the bootstrap artifact set.
- External discovery: NOT REQUIRED for governance installation; Authority 3.0 Notion package was the governing source.
- Stop/escalation conditions: Any missing or contradictory Authority package requirement, inability to preserve the adopted goal, or request to expand beyond governance installation.
- Source: User-authorized project bootstrap; Authority 3.0 Complete Installation Package in Notion.

---

## ANIMA-HA-P0-GOVERNANCE-BASELINE-001 — Reconcile and publish governed repository baseline

- Issued: 2026-08-28
- Status: COMPLETE
- Project stage: GOVERNANCE BASELINE
- Goal link: Establishes one observable, publicly safe, independently reviewable repository baseline before any ANIMA HA product implementation.
- Objective: Reconcile local Authority 3.0 state with the existing `SketchOTP/ANIMA-Home-Automation` repository and publish the governance-only checkpoint to `main`.
- Scope: Read and reconcile Authority state; initialize/configure local Git; preserve the remote baseline; correct repository pointers; review public safety; commit and push governance files; run installed validation; record checkpoint evidence in Authority and Notion.
- Exclusions: No product implementation, dependency scaffolding, services, APIs, schemas, UI, Home Assistant integration, prototype features, product-goal changes, or requirement weakening.
- Acceptance: Local `main` tracks the existing remote baseline; remote content is preserved; public safety review passes; Authority state records the GitHub repository and checkpoint; the adopted goal and completion marker remain intact; validation passes; working tree is clean; governance checkpoint is pushed; implementation file count remains zero.
- Required validation: Starting/final Git state, remote history/tree, public-material scan, installed Authority validation, clean working tree, remote SHA verification, and zero product implementation files.
- External discovery: NOT REQUIRED unless an unexpected Git/Authority issue requires authoritative documentation.
- Stop/escalation conditions: Meaningful history conflict, unclear sensitive-material publication, goal disagreement, uncorrectable validation failure, blocked authentication/permissions, or any need for implementation.
- Source: Architect directive `ANIMA-HA-P0-GOVERNANCE-BASELINE-001`.
