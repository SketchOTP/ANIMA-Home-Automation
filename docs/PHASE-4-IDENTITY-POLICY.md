# Phase 4 — Identity, Policy and Permission Engine

Status: implementation complete, pending Architect acceptance. This phase adds
the deterministic authority boundary only. It does not execute actions and does
not integrate Home Assistant, Luna, plugins, or voice identity.

## Boundary

`IdentityEvidence` describes evidence about a principal. `IdentityAggregator`
combines only non-expired evidence and returns an `IdentityContext`. Voice and
local proximity can reach `RECOGNIZED`, but cannot reach
`STRONG_AUTHENTICATED`. Conflicting principal claims resolve to anonymous,
conflicted context rather than a stronger identity.

`ActionIntent` is the proposed operation, before execution. Its risk class is
derived from the semantic action and canonical graph metadata:

| Risk class | Examples | Baseline result |
| --- | --- | --- |
| `READ_ONLY` | query temperature | Allow when scoped policy permits, including anonymous read in the synthetic baseline |
| `LOW_RISK_HOME_CONTROL` | turn a light off | Resident/guest control or explicit Anima autonomy |
| `SECURITY_SECURE_ACTION` | lock door, close garage | Explicit Anima autonomy or authenticated resident control |
| `SECURITY_ACCESS_ACTION` | unlock door, open garage | Strong authentication required; geofence/proximity is insufficient |
| `EXTERNAL_SIDE_EFFECT` | send message | Confirmation required, then exact confirmation can allow |
| `FINANCIAL_PURCHASE` | complete checkout | Explicit confirmation and authenticated principal required |
| `ADMIN_SYSTEM_PROHIBITED` | install package, edit policy, shell | Always denied |
| `UNKNOWN` | unclassified consequential operation | Denied fail-closed |

Household Graph roles are descriptive inputs. They grant no authority by
themselves. Memory is deliberately absent from the policy input; a remembered
preference cannot authorize an action. Explicit Anima autonomy is immutable
runtime configuration, not learned behavior.

## OPA boundary

OPA is a local replaceable evaluator. The ANIMA adapter constructs the input,
calls `/v1/data/anima/authorization/decision`, validates the structured result,
attaches the local policy bundle version/digest, and records the decision. OPA
does not own ANIMA principals, risk classes, identity evidence, audit records,
or policy mutation.

Selected image:

```text
openpolicyagent/opa:1.20.1@sha256:39daf255ae7f25d81103f03a0c18308a50b7b5bb67907bed6166f70e24a970ff
linux/amd64 manifest: sha256:4ea5e3f5c5fa36f300448c701d48a5411ee3b7eafe399ec58cf5fb777853ad86
linux/arm64 manifest: sha256:909992a577c26e3cc5ce996e81760c0786cf55bb5c3dc3f31476f76a30827427
```

The image is bound to loopback in Compose and loads repository policy files
read-only. No remote bundle, decision-log upload, telemetry service, or cloud
dependency is configured. Policy update remains a maintenance/commissioning
operation; no runtime Anima API can edit Rego, policy data, roles, prohibited
capabilities, or audit behavior.

OPA failure, malformed output, timeout, and unavailable policy all produce
`DENY` with `POLICY_UNAVAILABLE` or `POLICY_INVALID_RESULT`. The Python adapter
has no permissive fallback.

## Confirmation and audit

Confirmation challenges bind to one exact `ActionIntent`, principal, and
household, expire, and are consumed once. A challenge for another intent,
expired challenge, or consumed challenge cannot authorize the operation.

Identity evidence, policy-bundle metadata, and policy decisions persist in
PostgreSQL migration `0005_identity_policy.sql`. Each decision is also recorded
as a guaranteed `policy.decision` event in the existing Event Journal. The
stored snapshot contains reconstructive policy input and hashes, not raw
secrets, credentials, or biometric material.

## Prior-art decisions

| Candidate | Disposition | Reason |
| --- | --- | --- |
| OPA/Rego 1.20.1 | ADOPT / WRAP | Apache-2.0, current official amd64/arm64 artifacts, structured JSON results, local REST API, bundles, and `opa test`; wrapped so ANIMA owns domain semantics |
| Cedar | REFERENCE | Apache-2.0 and strong typed authorization model; native authorizer result is allow/deny, so it does not directly provide ANIMA's four-way result contract |
| Casbin | REFERENCE / REJECT as core | Useful embedded RBAC/ABAC library, but does not save enough work for ANIMA's contextual multi-result contract and adds policy ownership coupling |
| OpenFGA | DEFER / REJECT for Phase 4 | Relationship-tuple/ReBAC service is not needed for the current household policy scale; canonical graph remains the source of relationship facts |
| Direct Python policy | BUILD only for contracts/adapter/fail-closed wrapper | Keeping all policy semantics in Python would reduce policy-as-code replaceability; OPA owns evaluation while ANIMA owns the boundary |

Sources checked 2026-08-29: [OPA release](https://github.com/open-policy-agent/opa/releases/tag/v1.20.1), [OPA integration](https://www.openpolicyagent.org/docs/integration), [OPA Docker deployment](https://www.openpolicyagent.org/docs/deploy/docker), [OPA bundles](https://www.openpolicyagent.org/docs/management-bundles), [OPA testing](https://www.openpolicyagent.org/docs/policy-testing), [Cedar authorization](https://docs.cedarpolicy.com/auth/authorization.html), [Cedar implementation](https://github.com/cedar-policy/cedar), [OpenFGA concepts](https://openfga.dev/docs/concepts), and [Casbin documentation](https://casbin.org/).

## Evidence boundary

- Pure contract and failure-path tests: unit evidence.
- Rego syntax and four policy tests: OPA runtime evidence.
- PostgreSQL persistence, decision audit, confirmation consumption, and migration repeat: x86-64 PostgreSQL integration evidence.
- Simulator/API demonstrations: synthetic simulator evidence.
- OPA image index and per-platform manifests: ARM64/amd64 metadata evidence only.
- No physical identity, Home Assistant, Luna, real-door, or real-house authorization claim is made.
