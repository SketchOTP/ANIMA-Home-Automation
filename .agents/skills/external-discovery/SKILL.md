---
name: external-discovery
description: Search and evaluate relevant external prior art before substantial reinvention, difficult new engineering, rewrites, repeated failures, new domains, major course corrections, or novelty claims while preserving qualified existing work.
---

# External Discovery and Reuse

## Activation

Use this skill before substantial new capability/subsystem/framework/algorithm/model/agent mechanism/protocol/infrastructure/evaluation-system work, difficult custom mechanisms, major rewrites, repeated failed attempts, unfamiliar domains, major course corrections, material requirement changes, or novelty claims.

Routine fixes inside established architecture do not require exhaustive discovery.

## Search method

Search the underlying problem, not only project-specific names.

Use appropriate sources such as GitHub/GitLab, package registries, research papers/arXiv, Hugging Face/model hubs, standards/protocols, SDKs/APIs/frameworks, academic projects, benchmarks/datasets, and adjacent technical disciplines.

Scale research depth to the decision's cost and importance.

## Evaluate serious candidates

Consider functional overlap, architecture/API fit, license/provenance, maintenance/community maturity, security posture, tests/documentation, dependencies, determinism/performance limits, migration/integration cost, regression/revalidation cost, and long-term maintenance.

Classify material candidates as:

`ADOPT | WRAP | EXTEND | FORK | COMPOSE | REFERENCE | BENCHMARK | BUILD | REJECT`

## Existing qualified work

External discovery does not automatically authorize replacement. Preserve stable/qualified existing work unless the material future benefit justifies migration, regression, revalidation, dependency, governance, and maintenance costs.

If a discovery materially changes the strategic choice, return it to the Architect instead of silently re-architecting the project.

## Record

When discovery materially affects current/future decisions, append a concise entry to `.agent/EXTERNAL.md` including source, freshness, overlap, disposition, rationale, and recheck trigger.
