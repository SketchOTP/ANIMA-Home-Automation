import { useCallback, useEffect, useRef, useState } from "react";
import { Icon, Meter, StatusRing } from "./visuals";
import "./InitiativePanel.css";

const notificationTypes = [
  ["senseguard.opened", "Contact openings", "Qualified SenseGuard opening events"],
  ["household.presence.connection_changed", "Phone connection changes", "Connection evidence, not proof of a person’s arrival or departure"],
  ["household.ring.motion", "Ring motion", "Reported motion events, not video or person identification"],
  ["household.ring.doorbell", "Ring doorbell", "Reported doorbell events"],
] as const;
type DeviceNotificationRule = { resource_id: string; mode: "ALWAYS" | "TIME_WINDOW" | "NEVER" | "CONTEXTUAL"; start_local: string; end_local: string; timezone: string; event_kind?: "ANY" | "UNLOCKED" | "LOCKED" | "OPENED" | "CLOSED" | "MOTION" | "DOORBELL" };
type Config = { learning_days: number; routine_review_days: number; daily_review_enabled: boolean; routine_review_enabled: boolean; proactive_enabled: boolean; always_notify: string[]; device_notifications: DeviceNotificationRule[] };
type Snapshot = {
  config: Config; config_version: string | null; timezone: string; can_edit: boolean;
  readiness: { ready: boolean; observed_local_days: number; required_days: number; first_observed_at: string | null; last_observed_at: string | null; elapsed_seconds: number; required_elapsed_seconds: number; evidence_status: string; truncated: boolean };
  proactive_eligible: boolean; scheduling: { status: "NOT_SCHEDULED" | "SCHEDULED" | "PARTIAL"; tasks: unknown[] };
  running_status?: "AUTO_WAKE_DISABLED" | "AWAITING_SENTRY_CONSUMER";
  learning: {
    evidence_events: number; candidate_count: number; candidate_types: string[];
    candidates: Array<{ candidate_id: string; candidate_class: string; title: string; factual_summary: string; observation_count: number; distinct_day_count: number; elapsed_hours: number; maturity: string; missing_information: string[] }>;
    last_review: null | { review_id: string; review_kind: string; completed_at: string; candidate_count: number; outcome_count: number; evidence_start: string | null; evidence_end: string | null; authority: "NONE" };
    review_count: number; pending_review_count: number; gaps: string[];
  };
};
type Source = { event_id: string; event_type: string; occurred_at: string; recorded_at: string; canonical_id: string | null };
type Suggestion = {
  suggestion_id: string; kind: "PATTERN" | "WORKFLOW" | "LESSON"; content: string;
  confidence: number; classification: "INFERRED"; review_status: "PENDING" | "ACKNOWLEDGED" | "DISMISSED";
  source_refs: Source[]; created_at: string; authority: "NONE";
  conclusion?: string; candidate_class?: string | null; maturity?: string | null;
  maturity_evidence?: Record<string, unknown>; rationale_summary?: string | null;
  missing_information?: string[]; rejected_alternatives?: string[];
  knowledge_note?: { digest?: string } | null;
};
type Suggestions = { items: Suggestion[]; next_cursor: string | null };
export type InitiativePanelProps = { mutate: (path: string, payload?: Record<string, unknown>) => Promise<{ status: string; result?: unknown } | null>; onAuthFailure: () => void };
const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === "string" && value.length > 0;
const number = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value) && value >= 0;
const date = (value: unknown): value is string => text(value) && /(?:Z|[+-]\d\d:\d\d)$/.test(value) && Number.isFinite(Date.parse(value));
const nullableDate = (value: unknown) => value === null || date(value);
const inRange = (value: unknown, min: number, max: number) => number(value) && Number.isInteger(value) && value >= min && value <= max;
function parseSnapshot(value: unknown): Snapshot {
  if (!object(value) || value.status !== "SUCCEEDED" || value.authority !== "NONE" || !object(value.config) || !object(value.readiness) || !object(value.scheduling)) throw new Error("INVALID_RESPONSE");
  const config = value.config, ready = value.readiness, scheduling = value.scheduling;
  if (!inRange(config.learning_days, 3, 14) || !inRange(config.routine_review_days, 2, 14)
    || ![config.daily_review_enabled, config.routine_review_enabled, config.proactive_enabled, value.can_edit, value.proactive_eligible, ready.ready, ready.truncated].every(item => typeof item === "boolean")
    || !Array.isArray(config.always_notify) || !config.always_notify.every(type => notificationTypes.some(([id]) => id === type)) || new Set(config.always_notify).size !== config.always_notify.length
    || (config.device_notifications !== undefined && (!Array.isArray(config.device_notifications) || config.device_notifications.length > 128
    || !config.device_notifications.every(rule => object(rule) && text(rule.resource_id) && ["ALWAYS", "TIME_WINDOW", "NEVER", "CONTEXTUAL"].includes(String(rule.mode)) && /^\d\d:\d\d$/.test(String(rule.start_local)) && /^\d\d:\d\d$/.test(String(rule.end_local)) && text(rule.timezone) && (rule.event_kind === undefined || ["ANY", "UNLOCKED", "LOCKED", "OPENED", "CLOSED", "MOTION", "DOORBELL"].includes(String(rule.event_kind))))))
    || !(value.config_version === null || text(value.config_version)) || !text(value.timezone)
    || !inRange(ready.observed_local_days, 0, Number.MAX_SAFE_INTEGER) || !inRange(ready.required_days, 3, 14)
    || !nullableDate(ready.first_observed_at) || !nullableDate(ready.last_observed_at) || !number(ready.elapsed_seconds) || !number(ready.required_elapsed_seconds) || ready.required_elapsed_seconds === 0
    || !text(ready.evidence_status) || !/^[A-Z_]{1,64}$/.test(ready.evidence_status)
    || !["NOT_SCHEDULED", "SCHEDULED", "PARTIAL"].includes(String(scheduling.status)) || !Array.isArray(scheduling.tasks)
    || !(value.running_status === undefined || value.running_status === "AUTO_WAKE_DISABLED" || value.running_status === "AWAITING_SENTRY_CONSUMER")
    || !object(value.learning) || !number(value.learning.evidence_events) || !number(value.learning.candidate_count)
    || !number(value.learning.review_count) || !number(value.learning.pending_review_count)
    || !Array.isArray(value.learning.candidate_types) || !value.learning.candidate_types.every(text)
    || !Array.isArray(value.learning.candidates) || !Array.isArray(value.learning.gaps) || !value.learning.gaps.every(text)) throw new Error("INVALID_RESPONSE");
  return { ...value, config: { ...config, device_notifications: Array.isArray(config.device_notifications) ? config.device_notifications : [] } } as unknown as Snapshot;
}
function parseSuggestions(value: unknown): Suggestions {
  if (!object(value) || value.status !== "SUCCEEDED" || !Array.isArray(value.items) || !(value.next_cursor === null || text(value.next_cursor))) throw new Error("INVALID_RESPONSE");
  if (!value.items.every(item => object(item) && text(item.suggestion_id) && ["PATTERN", "WORKFLOW", "LESSON"].includes(String(item.kind))
    && text(item.content) && number(item.confidence) && item.confidence <= 1 && item.classification === "INFERRED" && item.authority === "NONE"
    && ["PENDING", "ACKNOWLEDGED", "DISMISSED"].includes(String(item.review_status)) && date(item.created_at) && Array.isArray(item.source_refs)
    && (item.conclusion === undefined || text(item.conclusion)) && (item.candidate_class === undefined || item.candidate_class === null || text(item.candidate_class))
    && (item.maturity === undefined || item.maturity === null || text(item.maturity)) && (item.maturity_evidence === undefined || object(item.maturity_evidence))
    && (item.rationale_summary === undefined || item.rationale_summary === null || text(item.rationale_summary))
    && (item.missing_information === undefined || (Array.isArray(item.missing_information) && item.missing_information.every(text)))
    && (item.rejected_alternatives === undefined || (Array.isArray(item.rejected_alternatives) && item.rejected_alternatives.every(text)))
    && (item.knowledge_note === undefined || item.knowledge_note === null || (object(item.knowledge_note) && (item.knowledge_note.digest === undefined || text(item.knowledge_note.digest))))
    && item.source_refs.every(source => object(source) && text(source.event_id) && text(source.event_type) && date(source.occurred_at) && date(source.recorded_at) && (source.canonical_id === null || text(source.canonical_id))))) throw new Error("INVALID_RESPONSE");
  if (new Set(value.items.map(item => item.suggestion_id)).size !== value.items.length) throw new Error("INVALID_RESPONSE");
  return value as unknown as Suggestions;
}
const timestamp = (value: string | null) => value ? new Date(value).toLocaleString() : "No observation recorded";
const hours = (seconds: number) => `${Math.round(seconds / 3600 * 10) / 10} h`;

export function InitiativePanel({ mutate, onAuthFailure }: InitiativePanelProps) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [draft, setDraft] = useState<Config | null>(null);
  const [draftVersion, setDraftVersion] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestions | null>(null);
  const [loading, setLoading] = useState(false), [busy, setBusy] = useState(false);
  const [error, setError] = useState(""), [suggestionError, setSuggestionError] = useState(""), [notice, setNotice] = useState("");
  const [reviewRequired, setReviewRequired] = useState(false);
  const [confirmation, setConfirmation] = useState<{ item: Suggestion; decision: "ACKNOWLEDGED" | "DISMISSED" } | null>(null);
  const auth = useRef(onAuthFailure); auth.current = onAuthFailure;
  const pending = useRef<AbortController | null>(null), generation = useRef(0), alive = useRef(true), lock = useRef(false);
  const draftRef = useRef(draft); draftRef.current = draft;
  const confirmHeading = useRef<HTMLHeadingElement>(null);
  const load = useCallback(async (cursor: string | null = null, replaceDraft = false) => {
    pending.current?.abort(); const abort = new AbortController(); pending.current = abort;
    const current = ++generation.current; setLoading(true); setError(""); setSuggestionError("");
    let timeout = false;
    const timer = window.setTimeout(() => { timeout = true; abort.abort(); }, 10_000);
    const read = async (path: string) => {
      const response = await fetch(path, { credentials: "same-origin", cache: "no-store", signal: abort.signal, headers: { Accept: "application/json" } });
      if (response.status === 401 || response.status === 403) throw new Error(String(response.status));
      if (!response.ok) throw new Error("UNAVAILABLE");
      return response.json() as Promise<unknown>;
    };
    try {
      const results = await Promise.allSettled([read("/api/v1/initiative").then(parseSnapshot), read(`/api/v1/initiative/suggestions?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`).then(parseSuggestions)]);
      if (current !== generation.current) return false;
      const denied = results.find(result => result.status === "rejected" && result.reason instanceof Error && ["401", "403"].includes(result.reason.message));
      if (denied?.status === "rejected") {
        setSnapshot(null); setDraft(null); draftRef.current = null; setDraftVersion(null); setSuggestions(null); setConfirmation(null); setNotice(""); setReviewRequired(false);
        if (denied.reason.message === "401") auth.current(); else setError("Access to SENTRY initiative is no longer allowed.");
        return false;
      }
      if (abort.signal.aborted) throw new Error("TIMEOUT");
      const [status, items] = results;
      if (status.status === "fulfilled") {
        setSnapshot(status.value);
        if (replaceDraft || !draftRef.current) { setDraft({ ...status.value.config, always_notify: [...status.value.config.always_notify], device_notifications: status.value.config.device_notifications.map(rule => ({ ...rule })) }); setDraftVersion(status.value.config_version); setReviewRequired(false); }
      } else { setSnapshot(null); setError("Initiative status could not be loaded. Settings draft kept; retry when Core is available."); }
      if (items.status === "fulfilled") setSuggestions(previous => ({ ...items.value, items: cursor && previous ? [...new Map([...previous.items, ...items.value.items].map(item => [item.suggestion_id, item])).values()] : items.value.items }));
      else { setSuggestions(null); setConfirmation(null); setSuggestionError("Learned suggestions are unavailable. No suggestion or evidence is being assumed."); }
      return status.status === "fulfilled" && items.status === "fulfilled";
    } catch {
      if (current === generation.current) { setSnapshot(null); setSuggestions(null); setConfirmation(null); setError(timeout ? "Initiative refresh timed out. Draft kept; retry when Core is available." : "Initiative could not be loaded. Draft kept; retry when Core is available."); }
      return false;
    } finally { window.clearTimeout(timer); if (current === generation.current) setLoading(false); }
  }, []);
  useEffect(() => { alive.current = true; void load(); return () => { alive.current = false; generation.current++; pending.current?.abort(); }; }, [load]);
  useEffect(() => { if (confirmation) confirmHeading.current?.focus(); }, [confirmation]);
  const change = async (operation: "configure" | "review", payload: Record<string, unknown>) => {
    if (lock.current || loading || !snapshot?.can_edit) return;
    lock.current = true; setBusy(true); setError(""); setNotice("");
    try {
      const result = await mutate(`/api/v1/initiative/${operation}`, payload);
      if (!alive.current) return;
      setConfirmation(null);
      const success = result?.status === "SUCCEEDED" && (!object(result.result) || !result.result.status || result.result.status === "SUCCEEDED");
      if (!success && operation === "configure") setReviewRequired(true);
      const refreshed = await load(null, success && operation === "configure");
      if (refreshed && alive.current) {
        if (success) setNotice(operation === "configure" ? "Initiative settings saved. This does not start automatic wake or prove notification delivery." : "Suggestion review saved. No action was executed and no owner-declared routine was created.");
        else setError("Change not confirmed. Review the refreshed state before another change; no automatic retry was sent.");
      }
    } catch {
      if (alive.current) { if (operation === "configure") setReviewRequired(true); setError("Change not confirmed. Draft kept; refresh and review before trying again. No automatic retry was sent."); }
    } finally { lock.current = false; if (alive.current) setBusy(false); }
  };
  const runCatchUp = async () => {
    if (lock.current || loading || !snapshot?.can_edit) return;
    lock.current = true; setBusy(true); setError(""); setNotice("");
    try {
      const result = await mutate("/api/v1/initiative/catch-up", {});
      if (!alive.current) return;
      if (result?.status === "QUEUED") setNotice("Initial catch-up queued through ANIMA Attention for SENTRY review. Suggestions remain non-executable until you review them.");
      else if (result?.status === "ALREADY_REQUESTED") setNotice("The initial catch-up was already requested. ANIMA will not duplicate it.");
      else setError("Catch-up was not queued. No review result is being assumed.");
      await load();
    } catch { if (alive.current) setError("Catch-up could not be queued. No automatic retry was sent."); }
    finally { lock.current = false; if (alive.current) setBusy(false); }
  };
  const update = <K extends keyof Config,>(key: K, value: Config[K]) => setDraft(previous => previous ? { ...previous, [key]: value } : null);
  const ready = snapshot?.readiness;
  const validDraft = draft && inRange(draft.learning_days, 3, 14) && inRange(draft.routine_review_days, 2, 14);
  return <section className="initiative-panel" aria-labelledby="initiative-title">
    <header className="initiative-header"><div><h2 id="initiative-title"><Icon name="Anima" />SENTRY initiative</h2><p className="muted">Observation first. Optional initiative after learning. You remain in control.</p></div><button type="button" disabled={busy || loading} onClick={() => void load()}><Icon name="Refresh" />{loading ? "Refreshing initiative…" : "Refresh initiative"}</button></header>
    {error && <p className="notice error" role="alert">{error}</p>}{notice && <p className="notice success" role="status">{notice}</p>}
    <div className="initiative-runtime"><Icon name="Pause" /><div><strong>{snapshot?.running_status === "AWAITING_SENTRY_CONSUMER" ? "Awaiting SENTRY consumer" : "Automatic wake disabled"}</strong><p>Configuration, eligibility, and scheduled tasks do not prove that reviews are running or notifications have been delivered.</p><small>{snapshot?.running_status ?? "AUTO_WAKE_DISABLED"} · No active worker is verified by this panel.</small></div></div>
    {!snapshot && !loading && <p className="empty-state">Collection and readiness are unavailable. No progress is assumed.</p>}
    {snapshot && ready && <div className="initiative-overview">
      <article className="card initiative-evidence"><StatusRing value={ready.observed_local_days} total={ready.required_days} label="Observed local days" valueLabel={`${ready.observed_local_days} / ${ready.required_days}`} size={116} />
        <div><h3>{ready.ready ? "Learning threshold met" : ready.observed_local_days ? "Collecting observation evidence" : "Waiting for observations"}</h3><p className="muted">{snapshot.timezone} · {ready.evidence_status.replaceAll("_", " ")}</p><Meter value={ready.elapsed_seconds} max={ready.required_elapsed_seconds} label="Evidence elapsed time" valueLabel={`${hours(ready.elapsed_seconds)} / ${hours(ready.required_elapsed_seconds)}`} />
          {ready.truncated && <p className="notice warning">Evidence scan is truncated. These are bounded results, not a complete household history.</p>}
          <details><summary>Observation provenance</summary><dl><dt>First observation</dt><dd>{timestamp(ready.first_observed_at)}</dd><dt>Last observation</dt><dd>{timestamp(ready.last_observed_at)}</dd></dl><p>Values come from Core’s observation evidence, not from time spent on this page.</p></details></div>
      </article>
      <article className="card"><h3><Icon name="Calendar" />Review scheduling</h3><strong>{({ NOT_SCHEDULED: "Not scheduled", SCHEDULED: "Scheduled — execution not verified", PARTIAL: "Partially scheduled" })[snapshot.scheduling.status]}</strong><p>{snapshot.scheduling.tasks.length} task records returned</p><p className="muted">Daily review: {snapshot.config.daily_review_enabled ? "enabled" : "disabled"}<br />Routine review: {snapshot.config.routine_review_enabled ? `every ${snapshot.config.routine_review_days} days` : "disabled"}</p><span className="status">{snapshot.proactive_eligible ? "Core eligibility met" : "Not eligible for optional initiative"}</span><p className="muted">Eligibility is not a running state or evidence of a notification.</p></article>
    </div>}
    {snapshot && <section className="card" aria-label="Household learning activity"><h3><Icon name="Chart" />What SENTRY is learning</h3>
      <p className="muted">ANIMA extracts source-linked candidates; SENTRY evaluates their meaning. These records are context only and cannot identify a person, grant authority, change Truth, or create a routine automatically.</p>
      <dl><dt>Qualified events considered</dt><dd>{snapshot.learning.evidence_events}</dd><dt>Current deterministic candidates</dt><dd>{snapshot.learning.candidate_count}</dd><dt>Completed reviews</dt><dd>{snapshot.learning.review_count}</dd><dt>Pending reviews</dt><dd>{snapshot.learning.pending_review_count}</dd><dt>Last review</dt><dd>{snapshot.learning.last_review ? `${snapshot.learning.last_review.review_kind.replaceAll("_", " ")} · ${timestamp(snapshot.learning.last_review.completed_at)}` : "No completed learning review yet"}</dd></dl>
      {snapshot.learning.candidates.length > 0 && <details><summary>Candidate patterns and maturity evidence</summary><ul className="clean-list list-spaced">{snapshot.learning.candidates.map(candidate => <li key={candidate.candidate_id}><strong>{candidate.title}</strong><p>{candidate.factual_summary}</p><small className="muted">{candidate.candidate_class.replaceAll("_", " ")} · {candidate.maturity.replaceAll("_", " ")} · {candidate.observation_count} observations · {candidate.distinct_day_count} local days · {Math.round(candidate.elapsed_hours * 10) / 10} h span</small></li>)}</ul></details>}
      {snapshot.learning.gaps.length > 0 && <details><summary>Evidence gaps preventing stronger conclusions</summary><ul>{snapshot.learning.gaps.map(gap => <li key={gap}>{gap}</li>)}</ul></details>}
      {snapshot.can_edit && <button type="button" disabled={busy || loading || snapshot.learning.review_count > 0 || snapshot.learning.pending_review_count > 0} onClick={() => void runCatchUp()}>{snapshot.learning.review_count || snapshot.learning.pending_review_count ? "Initial catch-up already requested" : "Run initial catch-up review"}</button>}
    </section>}
    {draft && <form className="card initiative-settings" onSubmit={event => { event.preventDefault(); if (validDraft && !reviewRequired) void change("configure", { ...draft, expected_version: draftVersion }); }}>
      <h3>Notification and learning policy</h3><p className="muted">Only an authenticated owner can save this policy. Preferences and learned suggestions never grant authority.</p>
      {reviewRequired && <div className="notice warning"><p>Settings draft retained. Compare it with the latest saved version before resubmitting.</p><button type="button" disabled={busy || loading} onClick={() => void load(null, true)}>Discard draft and load saved settings</button></div>}
      <fieldset disabled={!snapshot?.can_edit || busy || loading}><legend>Owner configuration</legend>
        <div className="initiative-settings-grid"><div><h4>Always notify for selected event types</h4><p className="muted">These selections are independent of optional proactive warmup. Existing explicit SenseGuard alert policies remain separate and are honored independently. A selection is not a delivery guarantee.</p>
          {notificationTypes.map(([id, label, detail]) => <label className="initiative-toggle" key={id}><span><strong>{label}</strong><small>{detail}</small></span><input type="checkbox" role="switch" aria-label={`Always notify: ${label}`} checked={draft.always_notify.includes(id)} onChange={() => update("always_notify", draft.always_notify.includes(id) ? draft.always_notify.filter(type => type !== id) : [...draft.always_notify, id])} /></label>)}
        </div><div><label className="initiative-toggle"><span><strong>Optional proactive notifications</strong><small>Only eligible after Core’s observation-learning gate; automatic wake remains disabled here.</small></span><input type="checkbox" role="switch" aria-label="Optional proactive notifications" checked={draft.proactive_enabled} onChange={event => update("proactive_enabled", event.target.checked)} /></label>
          <label className="initiative-field">Learning period (days)<input required type="number" min={3} max={14} step={1} value={Number.isFinite(draft.learning_days) ? draft.learning_days : ""} onChange={event => update("learning_days", event.target.valueAsNumber)} /><small>3–14 days. The saved policy’s current evidence is shown above.</small></label>
          <label className="initiative-toggle"><span><strong>Daily learning review</strong><small>Schedule one review per day.</small></span><input type="checkbox" role="switch" aria-label="Daily learning review" checked={draft.daily_review_enabled} onChange={event => update("daily_review_enabled", event.target.checked)} /></label>
          <label className="initiative-toggle"><span><strong>Routine review</strong><small>Review learned patterns and workflows without creating executable automations.</small></span><input type="checkbox" role="switch" aria-label="Routine review" checked={draft.routine_review_enabled} onChange={event => update("routine_review_enabled", event.target.checked)} /></label>
          <label className="initiative-field">Routine review interval (days)<input required type="number" min={2} max={14} step={1} value={Number.isFinite(draft.routine_review_days) ? draft.routine_review_days : ""} onChange={event => update("routine_review_days", event.target.valueAsNumber)} /><small>2–14 days.</small></label>
        </div></div><button type="submit" disabled={!validDraft || reviewRequired}>{busy ? "Saving…" : "Save initiative policy"}</button>
      </fieldset>
    </form>}
    <section className="card initiative-suggestions" aria-labelledby="initiative-suggestions-title"><h3 id="initiative-suggestions-title">Learned suggestions · not owner-declared routines</h3><p className="muted">Inferences for review only. Acknowledging does not approve execution, grant permission, or create a family routine.</p>
      {suggestionError && <p role="alert" className="notice error">{suggestionError}</p>}
      {suggestions && !suggestions.items.length && <p className="empty-state"><Icon name="Chart" />No learned suggestions recorded. No examples or inferred household facts have been filled in.</p>}
      {confirmation && <section role="group" aria-label="Confirm suggestion review" className="notice warning"><h4 ref={confirmHeading} tabIndex={-1}>{confirmation.decision === "ACKNOWLEDGED" ? "Acknowledge this inference?" : "Dismiss this inference?"}</h4><p>{confirmation.item.content}</p><p>This records your review only; nothing is executed.</p><div className="button-row"><button type="button" disabled={busy || loading} onClick={() => void change("review", { suggestion_id: confirmation.item.suggestion_id, decision: confirmation.decision })}>Confirm review</button><button type="button" disabled={busy} onClick={() => setConfirmation(null)}>Cancel review</button></div></section>}
      <ul className="clean-list initiative-suggestion-list">{suggestions?.items.map(item => <li key={item.suggestion_id}><div className="initiative-suggestion-header"><span className="status">{(item.conclusion ?? item.kind).replaceAll("_", " ").toLowerCase()}</span><span>{item.review_status.toLowerCase()}</span></div><p className="initiative-suggestion-content">{item.content}</p><p className="muted">{item.candidate_class?.replaceAll("_", " ") ?? "Legacy suggestion"} · {item.maturity?.replaceAll("_", " ") ?? "No deterministic maturity classification"}</p><Meter value={item.confidence} max={1} label="Model-reported confidence" valueLabel={`${Math.round(item.confidence * 100)}% · not certainty`} />
        <details><summary>Reasoning summary and maturity evidence</summary><p>{item.rationale_summary ?? "No structured rationale was recorded for this legacy suggestion."}</p>{item.maturity_evidence && <dl>{Object.entries(item.maturity_evidence).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd></div>)}</dl>}{item.missing_information?.length ? <><h4>Missing information</h4><ul>{item.missing_information.map(value => <li key={value}>{value}</li>)}</ul></> : null}{item.rejected_alternatives?.length ? <><h4>Rejected alternatives</h4><ul>{item.rejected_alternatives.map(value => <li key={value}>{value}</li>)}</ul></> : null}<p className="muted">{item.knowledge_note?.digest ? `Synced to Obsidian Memory · digest ${item.knowledge_note.digest.slice(0, 12)}…` : "No Obsidian Memory sync receipt is attached."}</p></details>
        <details><summary>Evidence &amp; provenance · {item.source_refs.length} source references</summary><p>Created {timestamp(item.created_at)} · Authority: none</p>{item.source_refs.length ? <ol>{item.source_refs.map((source, index) => <li key={`${source.event_id}-${index}`}><strong>{source.event_type}</strong><dl><dt>Occurred</dt><dd>{timestamp(source.occurred_at)}</dd><dt>Recorded</dt><dd>{timestamp(source.recorded_at)}</dd><dt>Event</dt><dd>{source.event_id}</dd><dt>Canonical resource</dt><dd>{source.canonical_id ?? "Not supplied"}</dd></dl></li>)}</ol> : <p>No source references supplied. This suggestion is not independently evidenced here.</p>}</details>
        {snapshot?.can_edit && item.review_status === "PENDING" && <div className="button-row"><button type="button" disabled={busy || loading} onClick={() => setConfirmation({ item, decision: "ACKNOWLEDGED" })}>Acknowledge suggestion</button><button type="button" disabled={busy || loading} onClick={() => setConfirmation({ item, decision: "DISMISSED" })}>Dismiss suggestion</button></div>}
      </li>)}</ul>
      {suggestions?.next_cursor && <button type="button" disabled={busy || loading} onClick={() => void load(suggestions.next_cursor)}>Load more suggestions</button>}
    </section>
  </section>;
}
