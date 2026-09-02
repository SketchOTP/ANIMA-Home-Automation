# Evidence

Status: `COMPLETE — PENDING ARCHITECT ACCEPTANCE` after the published
implementation and governed closure checkpoints; Architect review remains
outstanding.

Implementation checkpoint: `5d52c45c72520611de56361af9010419f2869c6c`.
Hosted CI: `33654654675` passed on that exact SHA.

Governed closure checkpoint: `bc7849dba3b65b837aacf2b16e8b7653fae97d08`.
Governed hosted CI: `33655337251` passed on that exact SHA.

The implementation uses `PostgresHouseholdGraph` provider references and
`MEMBER_OF` edges for identity, `PostgresRealityStore.projection` for Truth,
the Core `PluginManager` registry for capabilities, and the existing
PostgreSQL/OPA/Attention/Context/AgentRuntime composition.

Target command:

```bash
uv run python scripts/verify_phase12_commissioned_runtime.py
```

Observed local target: exact commissioned HA-user-to-person-to-household
mapping; real OPA task mutation; real OPA local-calendar mutation; real
Journal → Attention → ContextPacket → AgentRuntime conversation with distinct
event, trigger, and ContextPacket IDs; active UPCitemdb/qualified provider
registry; and explicit HA commissioning gate because no HA websocket/token was
configured on the test host.

Focused unit evidence: commissioned identity exact-one/missing/conflict tests,
normal non-test synthetic-map rejection, and PostgreSQL read-model tests that
fail if `DemoHouseholdReadModel` is called.

Evidence limits: scripted model adapter, synthetic commissioned graph fixture,
no live HA OAuth or physical-home execution, no native ARM64/Pi run, no
production TLS, and no live household data. The implementation checkpoint
contains the product changes; the subsequent governed closure commit records
this evidence packet and its exact-head CI. Architect acceptance is not claimed.
