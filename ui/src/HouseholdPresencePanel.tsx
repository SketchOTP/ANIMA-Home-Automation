import { useCallback, useEffect, useRef, useState } from "react";
import "./HouseholdPresencePanel.css";

type Member = { person_id: string; name: string };
type Signal = { binding_id: string; signal_kind: string; value: string; status: string; observed_at: string | null };
type Person = { person_id: string; value: string; status: string; binding_status: string; signals: Signal[] };
type Page = { items: Person[]; members: Member[]; can_edit: boolean; next_cursor: string | null };
type Source = { source_handle: string; name: string; signal_kind: string };
type Candidate = { candidate_handle: string; name: string; signal_kind: string; setup_status: string; enabled: boolean };
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
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [sourceCursor, setSourceCursor] = useState<string | null>(null);
  const [person, setPerson] = useState("");
  const [source, setSource] = useState("");
  const [freshness, setFreshness] = useState("900");
  const [candidate, setCandidate] = useState("");
  const [candidateName, setCandidateName] = useState("");
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
      const [presence, available, candidateResponse] = await Promise.all([
        fetch(`/api/v1/presence?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`, options),
        fetch(`/api/v1/presence/sources?limit=20${moreSources ? `&cursor=${encodeURIComponent(moreSources)}` : ""}`, options),
        fetch("/api/v1/presence/candidates", options),
      ]);
      if (current !== generation.current) return;
      if (presence.status === 401 || available.status === 401) { setPage(null); setSources([]); auth.current(); return; }
      if (!presence.ok || !available.ok) throw new Error("Presence unavailable. Check the Home Assistant connection; no location is being assumed.");
      const next = pageData(await presence.json());
      const sourcePage: unknown = await available.json();
      if (!object(sourcePage) || !Array.isArray(sourcePage.items)
        || !(sourcePage.next_cursor === null || typeof sourcePage.next_cursor === "string")
        || !sourcePage.items.every(item => object(item) && typeof item.source_handle === "string" && typeof item.name === "string" && typeof item.signal_kind === "string")) throw new Error("Invalid phone-source response");
      let candidateItems: Candidate[] = [];
      if (candidateResponse.ok) {
        const candidatePage: unknown = await candidateResponse.json();
        if (!object(candidatePage) || !Array.isArray(candidatePage.items)
          || !candidatePage.items.every(item => object(item) && typeof item.candidate_handle === "string"
            && typeof item.name === "string" && typeof item.signal_kind === "string"
            && typeof item.setup_status === "string" && typeof item.enabled === "boolean")) throw new Error("Invalid tracker-setup response");
        candidateItems = candidatePage.items as Candidate[];
      } else if (candidateResponse.status !== 403) throw new Error("Phone tracker setup is unavailable.");
      if (current !== generation.current || abort.signal.aborted) return;
      setPage(previous => ({ ...next, items: cursor && previous ? [...new Map([...previous.items, ...next.items].map(item => [item.person_id, item])).values()] : next.items }));
      setSources(previous => moreSources ? [...new Map([...previous, ...sourcePage.items as Source[]].map(item => [item.source_handle, item])).values()] : sourcePage.items as Source[]);
      setCandidates(candidateItems);
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
  const commission = async (event: React.FormEvent) => {
    event.preventDefault(); if (lock.current) return; lock.current = true; setBusy(true); setNotice("");
    try {
      const result = await mutate("/api/v1/presence/commission", { candidate_handle: candidate, name: candidateName });
      if (result?.status === "SUCCEEDED") {
        setNotice("Tracker enabled and commissioned. Assign it to the correct household member below after confirming which phone changed state.");
        setCandidate(""); setCandidateName(""); await load();
      }
    } finally { lock.current = false; setBusy(false); }
  };
  return <section className="presence-panel" aria-labelledby="presence-heading">
    <header><div><h2 id="presence-heading">Household presence</h2><p>Assign qualified Home Assistant phone geofence or supported Wi-Fi signals to household members, then review whether each signal currently suggests Home, Away, Not detected, or Unknown. ANIMA keeps freshness and conflicts visible; these signals are context for SENTRY, not authentication or proof of who caused an event.</p></div><button type="button" disabled={loading || busy} onClick={() => void load()}>{loading ? "Refreshing…" : "Refresh presence"}</button></header>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    <div className="presence-cards">{page?.items.map(item => <article key={item.person_id} data-presence={item.value}>
      <h3>{page.members.find(member => member.person_id === item.person_id)?.name ?? "Household member"}</h3>
      <strong>{labels[item.value]}</strong><small>{item.binding_status === "UNCONFIGURED" ? "Phone setup needed" : item.status.replaceAll("_", " ")}</small>
      {item.signals.map(signal => <p key={signal.binding_id}>{signal.signal_kind.replaceAll("_", " ")} · {labels[signal.value] ?? "Unknown"}<small>{signal.observed_at ? `HA updated ${new Date(signal.observed_at).toLocaleString()}` : "No fresh observation"}</small></p>)}
    </article>)}</div>
    {page?.next_cursor && <button type="button" disabled={loading || busy} onClick={() => void load(page.next_cursor)}>More household members</button>}
    {page && sources.length === 0 && !loading && <p className="presence-setup">No qualified phone trackers are assigned yet. Set up a discovered Home Assistant person or Wi-Fi tracker below, confirm its owner by observing a phone disconnect/reconnect, then assign it. A Wi-Fi disconnect alone does not prove someone left.</p>}
    {page?.can_edit && candidates.some(item => item.setup_status !== "COMMISSIONED") && <form onSubmit={event => void commission(event)}>
      <h3>Set up a phone tracker</h3>
      <p>ANIMA uses an opaque Home Assistant reference internally. Pick a tracker only after matching the device label or observing that it changes when the phone leaves and rejoins Wi-Fi.</p>
      <label>Discovered tracker<select required value={candidate} disabled={busy} onChange={event => {
        setCandidate(event.target.value);
        const selected = candidates.find(item => item.candidate_handle === event.target.value);
        setCandidateName(selected ? selected.name : "");
      }}><option value="">Choose tracker</option>{candidates.filter(item => item.setup_status !== "COMMISSIONED").map(item => <option key={item.candidate_handle} value={item.candidate_handle}>{item.name} · {item.enabled ? "enabled" : "needs enabling"}</option>)}</select></label>
      <label>ANIMA display name<input required maxLength={120} value={candidateName} disabled={busy} onChange={event => setCandidateName(event.target.value)} placeholder="Tym phone presence" /></label>
      <button disabled={busy || loading || !candidate || !candidateName.trim()}>{busy ? "Setting up…" : "Enable and commission tracker"}</button>
    </form>}
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
