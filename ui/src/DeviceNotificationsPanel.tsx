import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "./visuals";

type Mode = "ALWAYS" | "TIME_WINDOW" | "NEVER" | "CONTEXTUAL";
type SentryPath = "IMMEDIATE_ANNOUNCEMENT_ONLY" | "ANNOUNCEMENT_AND_CONTEXTUAL_REASONING" | "NO_SENTRY_REASONING";
type Rule = { resource_id: string; mode: Mode; start_local: string; end_local: string; timezone: string; event_kind?: "ANY" | "UNLOCKED" | "LOCKED" | "OPENED" | "CLOSED" | "MOTION" | "DOORBELL"; sentry_path?: SentryPath };
type InitiativeConfig = {
  learning_days: number; routine_review_days: number; daily_review_enabled: boolean;
  routine_review_enabled: boolean; proactive_enabled: boolean; always_notify: string[];
  device_notifications: Rule[];
};
type Snapshot = { status: string; can_edit: boolean; config_version: string | null; config: InitiativeConfig };
type Device = { device_handle: string; canonical_name?: string; metadata: Record<string, string | null> };
type Props = {
  devices: Device[];
  mutate: (path: string, payload?: Record<string, unknown>) => Promise<{ status: string } | null>;
  onAuthFailure: () => void;
};

const modes: { value: "DEFAULT" | Mode; label: string; help: string }[] = [
  { value: "DEFAULT", label: "Use household default", help: "Follow the shared alert and learning settings." },
  { value: "ALWAYS", label: "Always alert", help: "SENTRY must notify you for a qualified event from this device." },
  { value: "TIME_WINDOW", label: "Alert during set hours", help: "Always notify inside the selected household-local time window." },
  { value: "NEVER", label: "Never alert", help: "Record events, but do not interrupt you for this device." },
  { value: "CONTEXTUAL", label: "Let SENTRY decide", help: "Use the current event packet, routines, preferences, presence, and memory after learning is ready." },
];
const eventKinds: { value: NonNullable<Rule["event_kind"]>; label: string }[] = [
  { value: "ANY", label: "Any qualified event" },
  { value: "UNLOCKED", label: "Unlocked" },
  { value: "LOCKED", label: "Locked" },
  { value: "OPENED", label: "Opened" },
  { value: "CLOSED", label: "Closed" },
  { value: "MOTION", label: "Motion" },
  { value: "DOORBELL", label: "Doorbell press" },
];
const paths: { value: SentryPath; label: string; help: string }[] = [
  { value: "IMMEDIATE_ANNOUNCEMENT_ONLY", label: "Announce immediately · no Luna", help: "Use ANIMA's factual event sentence and do not spend an LLM turn." },
  { value: "ANNOUNCEMENT_AND_CONTEXTUAL_REASONING", label: "Announce + contextual reasoning", help: "Start the factual announcement immediately, then let SENTRY evaluate context in a separate turn." },
  { value: "NO_SENTRY_REASONING", label: "No SENTRY reasoning", help: "Keep the event as ANIMA evidence without waking SENTRY's reasoning provider." },
];
const emptyRule = (resource_id: string): Rule => ({ resource_id, mode: "CONTEXTUAL", start_local: "00:00", end_local: "05:00", timezone: "America/New_York", event_kind: "ANY" });

export function DeviceNotificationsPanel({ devices, mutate, onAuthFailure }: Props) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Rule | null>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const mounted = useRef(true);
  const authFailure = useRef(onAuthFailure);
  authFailure.current = onAuthFailure;
  const load = useCallback(async () => {
    setError("");
    const response = await fetch("/api/v1/initiative", { credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json" } });
    if (response.status === 401) { authFailure.current(); return; }
    if (!response.ok) throw new Error("Notification settings are unavailable.");
    const value = await response.json() as Snapshot;
    if (!value || value.status !== "SUCCEEDED" || !value.config || !Array.isArray(value.config.device_notifications)) throw new Error("Notification settings could not be read safely.");
    if (!mounted.current) return;
    setSnapshot(value);
    setDrafts(Object.fromEntries(devices.map(device => {
      const id = String(device.metadata.canonical_target_id ?? "");
      return [id, value.config.device_notifications.find(rule => rule.resource_id === id) ?? null];
    })));
  }, [devices]);
  useEffect(() => { mounted.current = true; void load().catch(reason => setError(reason instanceof Error ? reason.message : "Notification settings are unavailable.")); return () => { mounted.current = false; }; }, [load]);

  const save = async (resourceId: string) => {
    if (!snapshot || busy || !snapshot.can_edit) return;
    const selected = drafts[resourceId];
    const device_notifications = snapshot.config.device_notifications.filter(rule => rule.resource_id !== resourceId);
    if (selected) device_notifications.push(selected);
    setBusy(resourceId); setError(""); setNotice("");
    try {
      const result = await mutate("/api/v1/initiative/configure", { ...snapshot.config, device_notifications, expected_version: snapshot.config_version });
      if (result?.status !== "SUCCEEDED") { setError("The setting was not confirmed. Refresh before trying again."); return; }
      setNotice("Device alert setting saved.");
      await load();
    } finally { if (mounted.current) setBusy(null); }
  };

  const rows = devices.filter(device => device.metadata.mapping_status === "MAPPED" && device.metadata.canonical_target_id);
  const canEdit = snapshot?.can_edit === true;
  return <section className="card device-notifications" aria-labelledby="device-notifications-title">
    <div className="card-heading"><h2 id="device-notifications-title"><Icon name="Notifications" /> Device alert behavior</h2><button type="button" onClick={() => void load()} disabled={Boolean(busy)}><Icon name="Refresh" />Refresh</button></div>
    <p className="muted">Choose how SENTRY handles qualified events from each device. Events remain evidence; these settings control whether SENTRY should interrupt you.</p>
    <p className="muted">Processing paths: announce immediately without Luna; announce and run contextual reasoning; aggregate repeated low-urgency events into one reasoning turn; or keep the event in ANIMA without SENTRY reasoning. Aggregation is selected by ANIMA’s attention profile for high-volume event classes.</p>
    {error && <p className="notice error" role="alert">{error}</p>}{notice && <p className="notice success" role="status">{notice}</p>}
    {!snapshot && !error && <p role="status">Loading device alert settings…</p>}
    {snapshot && !snapshot.can_edit && <p className="notice warning">Only a household owner can change alert behavior.</p>}
    <div className="notification-device-grid">{rows.map(device => {
      const id = String(device.metadata.canonical_target_id);
      const draft = drafts[id] ?? null;
      const selected = draft?.mode ?? "DEFAULT";
      const definition = modes.find(item => item.value === selected)!;
      return <article className="notification-device-card" key={id}>
        <div><strong>{device.canonical_name ?? device.metadata.name ?? "Household device"}</strong><small>{device.metadata.manufacturer ?? device.metadata.integration ?? "ANIMA"}</small></div>
        <label>Alert behavior<select aria-label={`Alert behavior for ${device.canonical_name ?? device.metadata.name}`} value={selected} disabled={!canEdit || busy === id} onChange={event => {
          const mode = event.target.value as "DEFAULT" | Mode;
          setDrafts(current => ({ ...current, [id]: mode === "DEFAULT" ? null : { ...(current[id] ?? emptyRule(id)), mode } }));
        }}>{modes.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        <p>{definition.help}</p>
        {draft && <label>Event scope<select aria-label={`Event scope for ${device.canonical_name ?? device.metadata.name}`} value={draft.event_kind ?? "ANY"} disabled={!canEdit || busy === id} onChange={event => setDrafts(current => ({ ...current, [id]: { ...draft, event_kind: event.target.value as NonNullable<Rule["event_kind"]> } }))}>{eventKinds.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select><small>Choose the specific signal this rule applies to. Other signals continue to use the household default.</small></label>}
        {draft && <label>SENTRY processing path<select aria-label={`SENTRY processing path for ${device.canonical_name ?? device.metadata.name}`} value={draft.sentry_path ?? "ANNOUNCEMENT_AND_CONTEXTUAL_REASONING"} disabled={!canEdit || busy === id} onChange={event => setDrafts(current => ({ ...current, [id]: { ...draft, sentry_path: event.target.value as SentryPath } }))}>{paths.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select><small>{paths.find(item => item.value === (draft.sentry_path ?? "ANNOUNCEMENT_AND_CONTEXTUAL_REASONING"))?.help}</small></label>}
        {draft?.mode === "TIME_WINDOW" && <div className="notification-time-grid"><label>From<input type="time" value={draft.start_local} onChange={event => setDrafts(current => ({ ...current, [id]: { ...draft, start_local: event.target.value } }))} /></label><label>Until<input type="time" value={draft.end_local} onChange={event => setDrafts(current => ({ ...current, [id]: { ...draft, end_local: event.target.value } }))} /></label></div>}
        <button type="button" className="primary" disabled={!canEdit || busy === id} onClick={() => void save(id)}>{busy === id ? "Saving…" : "Save alert setting"}</button>
      </article>;
    })}</div>
    {snapshot && !rows.length && <p className="empty-state">Commission a device before setting its alert behavior.</p>}
  </section>;
}
