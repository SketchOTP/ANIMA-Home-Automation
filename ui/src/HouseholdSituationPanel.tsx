import { useCallback, useEffect, useRef, useState } from "react";

type Snapshot = {
  status: "SUCCEEDED"; authority: "NONE"; can_edit: boolean;
  declared_mode: { mode: "HOME" | "AWAY" | "UNSET"; version: string | null; declared_at: string | null };
  inventory: Array<{ canonical_id: string; kind: string; name: string }>;
  observations: { items: Array<{ event_id: string; event_type: string; recorded_at: string; time_basis: string; physical_occurred_at: null }>; truncated: boolean };
  source_coverage: { ha_bound_consumer: { status: string; coverage: string }; android: { status: string; coverage: string }; handoff: { status: string } };
  incidents: Array<{ incident_id: string; assessment: string; unknowns: string[]; classification: string; request_lifecycle: string; required_delivery: { state?: string; human_receipt: string }; response_ledger: Array<{ action_id: string; status: string; verification: string }> }>;
};
type Props = { mutate: (path: string, payload?: Record<string, unknown>) => Promise<{ status: string; result?: unknown } | null>; onAuthFailure: () => void; readOnly?: boolean };
const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
function parse(value: unknown): Snapshot {
  if (!object(value) || value.status !== "SUCCEEDED" || value.authority !== "NONE" || typeof value.can_edit !== "boolean"
    || !object(value.declared_mode) || !["HOME", "AWAY", "UNSET"].includes(String(value.declared_mode.mode))
    || !(value.declared_mode.version === null || typeof value.declared_mode.version === "string")
    || !(value.declared_mode.declared_at === null || typeof value.declared_mode.declared_at === "string")
    || !Array.isArray(value.inventory) || !value.inventory.every(item => object(item) && [item.canonical_id, item.kind, item.name].every(text => typeof text === "string"))
    || !object(value.observations) || !Array.isArray(value.observations.items) || typeof value.observations.truncated !== "boolean"
    || !value.observations.items.every(item => object(item) && item.physical_occurred_at === null && [item.event_id, item.event_type, item.recorded_at, item.time_basis].every(text => typeof text === "string"))
    || !object(value.source_coverage) || !object(value.source_coverage.ha_bound_consumer) || !object(value.source_coverage.android) || !object(value.source_coverage.handoff)
    || ![value.source_coverage.ha_bound_consumer.status, value.source_coverage.android.status, value.source_coverage.handoff.status].every(text => typeof text === "string")
    || !Array.isArray(value.incidents) || !value.incidents.every(item => object(item) && [item.incident_id, item.assessment, item.classification, item.request_lifecycle].every(text => typeof text === "string")
      && Array.isArray(item.unknowns) && item.unknowns.every(text => typeof text === "string") && object(item.required_delivery)
      && Array.isArray(item.response_ledger) && item.response_ledger.every(action => object(action) && [action.action_id, action.status, action.verification].every(text => typeof text === "string")))) throw new Error("INVALID_HOUSEHOLD_CONTEXT");
  return value as unknown as Snapshot;
}

export function HouseholdSituationPanel({ mutate, onAuthFailure, readOnly = false }: Props) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null), [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reloadRequired, setReloadRequired] = useState(false);
  const auth = useRef(onAuthFailure); auth.current = onAuthFailure;
  const generation = useRef(0), lock = useRef(false), alive = useRef(true);
  const load = useCallback(async (signal?: AbortSignal) => {
    const current = ++generation.current;
    try {
      const response = await fetch("/api/v1/initiative/situation", { credentials: "same-origin", signal });
      if (response.status === 401) { auth.current(); return; }
      if (!response.ok) throw new Error("HOUSEHOLD_CONTEXT_UNAVAILABLE");
      const value = parse(await response.json());
      if (alive.current && current === generation.current) { setSnapshot(value); setError(""); setReloadRequired(false); }
    } catch {
      if (!signal?.aborted && alive.current && current === generation.current) { setSnapshot(null); setError("Household context unavailable; quiet or occupancy cannot be inferred."); }
    }
  }, []);
  useEffect(() => { alive.current = true; const controller = new AbortController(); void load(controller.signal); return () => { alive.current = false; ++generation.current; controller.abort(); }; }, [load]);
  const declare = async (mode: "HOME" | "AWAY" | "UNSET") => {
    if (!snapshot?.can_edit || readOnly || lock.current || reloadRequired) return;
    lock.current = true; setBusy(true);
    ++generation.current;
    try {
      const outcome = await mutate("/api/v1/initiative/set_household_mode", { mode, expected_version: snapshot.declared_mode.version });
      if (outcome?.status !== "SUCCEEDED" || !object(outcome.result) || outcome.result.status !== "SUCCEEDED") throw new Error("DECLARATION_NOT_CONFIRMED");
      await load();
    } catch {
      if (alive.current) { setError("Declaration not confirmed. Reload and review the current version; no automatic retry."); setReloadRequired(true); }
    } finally { lock.current = false; if (alive.current) setBusy(false); }
  };
  return <section className="card" aria-label="Household context"><h2>Household context</h2>
    <p className="muted">Declared mode is your explicit expectation, not authentication, permission, or inferred occupancy. Phone absence never selects Away.</p>
    {error && <p role="alert">{error}</p>}
    <button type="button" disabled={busy} onClick={() => void load()}>Refresh context</button>
    {snapshot && <><p>Owner-declared mode: <strong>{snapshot.declared_mode.mode}</strong> · {snapshot.declared_mode.declared_at ? new Date(snapshot.declared_mode.declared_at).toLocaleString() : "No declaration"}</p>
      {!readOnly && snapshot.can_edit && <div className="button-row">{(["HOME", "AWAY", "UNSET"] as const).map(mode => <button key={mode} type="button" disabled={busy || reloadRequired} aria-pressed={snapshot.declared_mode.mode === mode} onClick={() => void declare(mode)}>Declare {mode.toLowerCase()}</button>)}</div>}
      <p>{snapshot.inventory.length} commissioned inventory entries · {snapshot.observations.items.length} observations in the bounded 10-minute window{snapshot.observations.truncated ? " (truncated)" : ""}. Counts are not coverage uptime.</p>
      <dl className="settings-grid"><dt>Bound HA consumer</dt><dd>{snapshot.source_coverage.ha_bound_consumer.status}</dd><dt>Android coverage</dt><dd>{snapshot.source_coverage.android.status}</dd><dt>Journal handoff</dt><dd>{snapshot.source_coverage.handoff.status}</dd></dl>
      <p className="muted">Old transition timestamps are history, not heartbeat. Missing events do not prove healthy quiet. Receipt/process times do not prove physical occurrence or audible start.</p>
      <details><summary>Qualified recent observations</summary><ul className="clean-list">{snapshot.observations.items.map(item => <li key={item.event_id}>{item.event_type} · received {new Date(item.recorded_at).toLocaleString()} · {item.time_basis} · physical time unknown</li>)}</ul></details>
      <h3>Source-linked assessments</h3><p className="muted">SENTRY inference is not an intruder conclusion or action authority. Existing device notification routes select contextual reasoning; immediate-only speech gains no commentary.</p>
      {snapshot.incidents.length ? snapshot.incidents.map(item => <article key={item.incident_id}><p>{item.assessment}</p><p>{item.classification} · request {item.request_lifecycle} · speech {item.required_delivery.state ?? "NOT_MANAGED"}; human receipt unverified</p><ul>{item.unknowns.map((unknown, index) => <li key={index}>{unknown}</li>)}</ul><ul>{item.response_ledger.map(action => <li key={action.action_id}>{action.status} · {action.verification}</li>)}</ul></article>) : <p>No recorded assessment in this bounded view; not proof of no incident.</p>}
    </>}
  </section>;
}
