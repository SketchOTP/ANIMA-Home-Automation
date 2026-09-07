import { useCallback, useEffect, useRef, useState } from "react";
import "./HouseholdPresencePanel.css";

type Member = { person_id: string; name: string };
type Signal = { binding_id: string; signal_kind: string; value: string; status: string; observed_at: string | null };
type Person = { person_id: string; value: string; status: string; binding_status: string; signals: Signal[] };
type Page = { items: Person[]; members: Member[]; can_edit: boolean; next_cursor: string | null };
type Source = { source_handle: string; name: string; signal_kind: string };
type Props = {
  mutate: (path: string, payload?: Record<string, unknown>) => Promise<{ status: string } | null>;
  onAuthFailure: () => void;
};
const labels: Record<string, string> = { HOME: "Home signal", AWAY: "Outside home zone", NOT_DETECTED: "Not detected", UNKNOWN: "Unknown" };
const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);
function pageData(value: unknown): Page {
  if (!object(value) || !Array.isArray(value.items) || !Array.isArray(value.members) || typeof value.can_edit !== "boolean"
    || !(value.next_cursor === null || typeof value.next_cursor === "string")
    || !value.members.every(item => object(item) && typeof item.person_id === "string" && typeof item.name === "string")
    || !value.items.every(item => object(item) && typeof item.person_id === "string" && typeof item.status === "string"
      && typeof item.value === "string" && item.value in labels && typeof item.binding_status === "string" && Array.isArray(item.signals)
      && item.signals.every(signal => object(signal) && typeof signal.binding_id === "string" && typeof signal.signal_kind === "string"
        && typeof signal.status === "string" && typeof signal.value === "string" && (signal.observed_at === null || typeof signal.observed_at === "string")))) throw new Error("Invalid presence response");
  return value as Page;
}

export function HouseholdPresencePanel({ mutate, onAuthFailure }: Props) {
  const [page, setPage] = useState<Page | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [sourceCursor, setSourceCursor] = useState<string | null>(null);
  const [person, setPerson] = useState("");
  const [source, setSource] = useState("");
  const [freshness, setFreshness] = useState("900");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const lock = useRef(false);
  const auth = useRef(onAuthFailure); auth.current = onAuthFailure;
  const load = useCallback(async (cursor: string | null = null, moreSources: string | null = null) => {
    controller.current?.abort(); const abort = new AbortController(); controller.current = abort;
    const current = ++generation.current; setLoading(true); setError("");
    const timer = window.setTimeout(() => abort.abort(), 10000);
    try {
      const options = { credentials: "same-origin" as const, cache: "no-store" as const, signal: abort.signal };
      const [presence, available] = await Promise.all([
        fetch(`/api/v1/presence?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`, options),
        fetch(`/api/v1/presence/sources?limit=20${moreSources ? `&cursor=${encodeURIComponent(moreSources)}` : ""}`, options),
      ]);
      if (current !== generation.current) return;
      if (presence.status === 401 || available.status === 401) { setPage(null); setSources([]); auth.current(); return; }
      if (!presence.ok || !available.ok) throw new Error("Presence unavailable. Check the Home Assistant connection; no location is being assumed.");
      const next = pageData(await presence.json());
      const sourcePage: unknown = await available.json();
      if (!object(sourcePage) || !Array.isArray(sourcePage.items)
        || !(sourcePage.next_cursor === null || typeof sourcePage.next_cursor === "string")
        || !sourcePage.items.every(item => object(item) && typeof item.source_handle === "string" && typeof item.name === "string" && typeof item.signal_kind === "string")) throw new Error("Invalid phone-source response");
      if (current !== generation.current || abort.signal.aborted) return;
      setPage(previous => ({ ...next, items: cursor && previous ? [...new Map([...previous.items, ...next.items].map(item => [item.person_id, item])).values()] : next.items }));
      setSources(previous => moreSources ? [...new Map([...previous, ...sourcePage.items as Source[]].map(item => [item.source_handle, item])).values()] : sourcePage.items as Source[]);
      setSourceCursor(sourcePage.next_cursor as string | null);
    } catch (reason) {
      if (current === generation.current) { setPage(null); setSources([]); setError(reason instanceof Error && reason.name !== "AbortError" ? reason.message : "Presence refresh timed out. Retry when Core is available."); }
    } finally { window.clearTimeout(timer); if (current === generation.current) setLoading(false); }
  }, []);
  useEffect(() => { void load(); return () => { generation.current++; controller.current?.abort(); }; }, [load]);
  const bind = async (event: React.FormEvent) => {
    event.preventDefault(); if (lock.current) return; lock.current = true; setBusy(true); setNotice("");
    try {
      const result = await mutate("/api/v1/presence/bind", { person_id: person, source_handle: source, freshness_seconds: Number(freshness) });
      if (result?.status === "SUCCEEDED") { setNotice("Phone source assigned. Presence remains evidence, not authentication."); setSource(""); await load(); }
    } finally { lock.current = false; setBusy(false); }
  };
  return <section className="presence-panel" aria-labelledby="presence-heading">
    <header><div><h2 id="presence-heading">Household presence</h2><p>Phone geofencing + Wi-Fi connection evidence</p></div><button type="button" disabled={loading || busy} onClick={() => void load()}>{loading ? "Refreshing…" : "Refresh presence"}</button></header>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    <div className="presence-cards">{page?.items.map(item => <article key={item.person_id} data-presence={item.value}>
      <h3>{page.members.find(member => member.person_id === item.person_id)?.name ?? "Household member"}</h3>
      <strong>{labels[item.value]}</strong><small>{item.binding_status === "UNCONFIGURED" ? "Phone setup needed" : item.status.replaceAll("_", " ")}</small>
      {item.signals.map(signal => <p key={signal.binding_id}>{signal.signal_kind.replaceAll("_", " ")} · {labels[signal.value] ?? "Unknown"}<small>{signal.observed_at ? `HA updated ${new Date(signal.observed_at).toLocaleString()}` : "No fresh observation"}</small></p>)}
    </article>)}</div>
    {page?.next_cursor && <button type="button" disabled={loading || busy} onClick={() => void load(page.next_cursor)}>More household members</button>}
    {page && sources.length === 0 && !loading && <p className="presence-setup">No qualified phone trackers are available yet. Connect the Home Assistant phone app or a supported router integration, commission the discovered phone source in Devices, then assign it here. A Wi-Fi disconnect alone does not prove someone left.</p>}
    {page?.can_edit && sources.length > 0 && <form onSubmit={event => void bind(event)}>
      <label>Household member<select required value={person} disabled={busy} onChange={event => setPerson(event.target.value)}><option value="">Choose member</option>{page.members.map(member => <option key={member.person_id} value={member.person_id}>{member.name}</option>)}</select></label>
      <label>Phone presence source<select required value={source} disabled={busy} onChange={event => setSource(event.target.value)}><option value="">Choose source</option>{sources.map(item => <option key={item.source_handle} value={item.source_handle}>{item.name} · {item.signal_kind.replaceAll("_", " ")}</option>)}</select></label>
      <label>Maximum observation age (seconds)<input type="number" min="30" max="86400" required value={freshness} disabled={busy} onChange={event => setFreshness(event.target.value)} /></label>
      <button disabled={busy || loading || !person || !source}>{busy ? "Assigning…" : "Assign phone source"}</button>
    </form>}
    {sourceCursor && <button type="button" disabled={busy || loading} onClick={() => void load(null, sourceCursor)}>More phone sources</button>}
    <p className="presence-caveat">Wi-Fi reconnects can indicate a return; disconnects can also mean sleep, poor coverage or router failure. SENTRY must compare fresh signals and routines. A phone does not identify who opened a door.</p>
  </section>;
}
