import { useEffect, useRef, useState } from "react";
import { Icon } from "./visuals";
import "./KnowledgePanel.css";

type Outcome = { status: string; reason?: string; detail?: string; result?: unknown };
type SourceRef = { kind: string; source_id: string; meaning: string };
type Note = {
  note_id: string; digest: string; status: string; title?: string; body?: string;
  note_type?: string; classifier?: string; classification: string; confidence?: number;
  source_refs?: SourceRef[]; observed_at?: string | null; enabled: boolean;
  retention_days?: number | null; person_refs?: string[]; created_at: string; updated_at: string; expires_at: string | null;
};
type NotePage = { items: Note[]; next_cursor: string | null; truncated?: boolean };
type Member = { person_id: string; name: string };
type MemoryStatus = { agent_memory_enabled?: boolean; available?: boolean; writer_status?: string; decision_journal?: string };
type Draft = {
  title: string; body: string; note_type: string; classifier: string; classification: string;
  confidence: string; observed_at: string; enabled: boolean; retention_days: string;
  source_refs: SourceRef[]; person_refs: string[];
};
const blank = (): Draft => ({ title: "", body: "", note_type: "event", classifier: "640",
  classification: "SENTRY_INFERENCE", confidence: "0.5", observed_at: "", enabled: true,
  retention_days: "", person_refs: [], source_refs: [{ kind: "event", source_id: "", meaning: "" }] });
const label = (value: string) => value.toLowerCase().replaceAll("_", " ");

export function KnowledgePanel({ mutate, onAuthFailure }: {
  mutate: (path: string, payload?: Record<string, unknown>) => Promise<Outcome | null>;
  onAuthFailure: () => void;
}) {
  const [items, setItems] = useState<Note[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [personFilter, setPersonFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [members, setMembers] = useState<Member[]>([]);
  const [membersAvailable, setMembersAvailable] = useState(false);
  const [memoryStatus, setMemoryStatus] = useState<MemoryStatus | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [selected, setSelected] = useState<Note | null>(null);
  const [editing, setEditing] = useState<Note | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [draft, setDraft] = useState<Draft>(blank);
  const mounted = useRef(false);
  const readGeneration = useRef(0);
  const abort = useRef<AbortController | null>(null);
  const writing = useRef(false);
  const authFailure = useRef(onAuthFailure); authFailure.current = onAuthFailure;
  const loadRef = useRef<(cursor?: string | null) => Promise<void>>(async () => {});

  async function read<T>(path: string, controller: AbortController): Promise<T> {
    const response = await fetch(path, { credentials: "same-origin", signal: controller.signal,
      headers: { Accept: "application/json" } });
    if (response.status === 401 && mounted.current && !controller.signal.aborted) {
      setItems([]); setSelected(null); setDraft(blank()); setFormOpen(false); setMembers([]); setMemoryStatus(null);
      authFailure.current(); throw new Error("Your session has expired.");
    }
    if (!response.ok) {
      throw new Error(response.status === 409 ? "A memory note has an unreconciled external edit or a busy writer. Its file was preserved. Reconcile the edit before retrying; no automatic import was performed."
        : response.status === 403 ? "Memory access was denied."
        : "Memory is not configured or is unavailable. Ask the administrator to check the existing vault connection.");
    }
    return response.json() as Promise<T>;
  }
  async function load(cursor: string | null = null) {
    if (!mounted.current || document.hidden || writing.current) return;
    const generation = ++readGeneration.current;
    abort.current?.abort(); const controller = new AbortController(); abort.current = controller;
    const timeout = window.setTimeout(() => controller.abort(), 10000);
    setLoading(true);
    try {
      const path = search ? `/api/v1/knowledge-search?limit=20&${search}`
        : `/api/v1/knowledge?limit=50${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`;
      const [page, status, family] = await Promise.all([
        read<NotePage>(path, controller),
        read<MemoryStatus>("/api/v1/knowledge-status", controller).catch(() => null),
        read<{ members: Member[] }>("/api/v1/family-routines?limit=1", controller).catch(() => null),
      ]);
      if (!mounted.current || generation !== readGeneration.current) return;
      if (!Array.isArray(page.items)) throw new Error("Memory returned an unreadable result.");
      setItems(current => cursor ? [...current, ...page.items.filter(item => !current.some(old => old.note_id === item.note_id))] : page.items);
      setNextCursor(search ? null : page.next_cursor); setTruncated(page.truncated === true);
      setMemoryStatus(status && typeof status.agent_memory_enabled === "boolean" ? status : null);
      const validMembers = Array.isArray(family?.members) && family.members.every(member => typeof member.person_id === "string" && typeof member.name === "string");
      setMembers(validMembers ? family!.members : []); setMembersAvailable(validMembers);
      setLoaded(true); setError("");
    } catch (failure) {
      if (mounted.current && generation === readGeneration.current) {
        setError(controller.signal.aborted ? "Memory refresh timed out. Try Refresh memory."
          : failure instanceof Error ? failure.message : "Memory could not be refreshed.");
      }
    } finally {
      window.clearTimeout(timeout);
      if (mounted.current && generation === readGeneration.current) setLoading(false);
      if (abort.current === controller) abort.current = null;
    }
  }
  loadRef.current = load;
  useEffect(() => {
    mounted.current = true; void loadRef.current();
    const refresh = () => { if (!document.hidden && document.hasFocus()) void loadRef.current(); };
    const visibility = () => {
      if (document.hidden) { readGeneration.current++; abort.current?.abort(); setLoading(false); }
      else refresh();
    };
    window.addEventListener("focus", refresh); document.addEventListener("visibilitychange", visibility);
    const timer = window.setInterval(refresh, 30000);
    return () => { mounted.current = false; readGeneration.current++; abort.current?.abort();
      window.clearInterval(timer); window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", visibility); };
  }, [search]);
  async function open(note: Note) {
    const generation = ++readGeneration.current;
    abort.current?.abort(); const controller = new AbortController(); abort.current = controller;
    const timeout = window.setTimeout(() => controller.abort(), 10000);
    setLoading(true);
    try {
      const result = await read<{ note: Note }>(`/api/v1/knowledge/${note.note_id}`, controller);
      if (mounted.current && generation === readGeneration.current) { setSelected(result.note); setError(""); }
    } catch (failure) {
      if (mounted.current && generation === readGeneration.current) setError(controller.signal.aborted
        ? "Reading the note timed out. Try again." : failure instanceof Error ? failure.message : "Note unavailable.");
    } finally { window.clearTimeout(timeout); if (mounted.current && generation === readGeneration.current) setLoading(false); }
  }
  function edit(note: Note) {
    setEditing(note); setDraft({ title: note.title ?? "", body: note.body ?? "",
      note_type: note.note_type ?? "event", classifier: note.classifier ?? "640",
      classification: note.classification, confidence: String(note.confidence ?? 0.5),
      observed_at: note.observed_at ?? "", enabled: note.enabled,
      retention_days: note.retention_days == null ? "" : String(note.retention_days),
      person_refs: note.person_refs ?? [], source_refs: note.source_refs ?? [] });
    setFormOpen(true); setNotice("");
  }
  async function write(action: string, payload: Record<string, unknown>) {
    if (writing.current) return;
    writing.current = true; setBusy(true); setNotice("");
    try {
      const result = await mutate(`/api/v1/knowledge/${action}`, payload);
      if (!mounted.current) return;
      if (result?.status === "SUCCEEDED") {
        setNotice(action === "retract" ? "Note retracted. Its active file is a prose-free tombstone; backups and prior transcripts are not erased." : "Core confirmed the note change.");
        setFormOpen(false); setEditing(null); setSelected(null); setDraft(blank());
      } else setNotice(result?.reason === "KnowledgeConflict" ? "Conflict: the note changed or another writer is active. Your draft and the existing file were preserved. Reload before retrying."
        : result ? `${result.status}: ${result.detail ?? result.reason ?? "Core did not confirm the change."}` : "The change was not confirmed. No automatic retry was sent.");
    } catch {
      if (mounted.current) setNotice("The change was not confirmed. Your draft is preserved; no automatic retry was sent.");
    } finally {
      writing.current = false;
      if (mounted.current) { setBusy(false); void loadRef.current(); }
    }
  }
  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (new TextEncoder().encode(draft.body).length > 4096) { setNotice("Note text must be at most 4 KiB."); return; }
    if (draft.classification === "USER_STATED" && !draft.source_refs.some(source => source.kind === "request")) {
      setNotice("A user-stated claim needs an attributed request source. This does not verify the claim."); return;
    }
    let observed: string | null = null;
    if (draft.observed_at) {
      const date = new Date(draft.observed_at);
      if (!Number.isFinite(date.getTime()) || !/(Z|[+-]\d\d:\d\d)$/.test(draft.observed_at)) { setNotice("Observed at needs an ISO timestamp with timezone, such as UTC ending in Z."); return; }
      observed = date.toISOString();
    }
    const payload: Record<string, unknown> = { ...draft, confidence: Number(draft.confidence), retention_days: draft.retention_days === "" ? null : Number(draft.retention_days), observed_at: observed,
      ...(editing ? { note_id: editing.note_id, expected_digest: editing.digest } : {}) };
    // A prose correction must not silently restart an existing retention clock.
    if (editing && draft.retention_days === (editing.retention_days == null ? "" : String(editing.retention_days))) delete payload.retention_days;
    void write(editing ? "update" : "create", payload);
  }
  const update = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft(current => ({ ...current, [key]: value }));
  return <section className="card knowledge-panel" aria-label="Memory knowledge base">
    <div className="card-heading"><h2><Icon name="Preferences" />Memory · Knowledge base</h2></div>
    <p className="muted">Long-term notes in the existing MEMORY vault. This includes owner-curated knowledge, SENTRY's useful learned notes, and an internal decision journal for eligible turns. Decision entries show conclusions, evidence categories, tool outcomes and uncertainty—not hidden chain-of-thought, raw prompts or transcripts.</p>
    <p className="knowledge-status" role="status">{memoryStatus
      ? `Agent memory ${memoryStatus.agent_memory_enabled ? "eligible by configuration" : "disabled by configuration"}. Storage ${memoryStatus.available === true ? "available" : memoryStatus.available === false ? "unavailable" : "availability unknown"}. Decision journal ${memoryStatus.decision_journal === "ENABLED_FOR_ELIGIBLE_TURNS" ? "enabled for eligible SENTRY turns" : "not enabled"}.`
      : "Agent memory status unavailable; automatic capture is not established."}</p>
    <div className="button-row"><button type="button" disabled={loading || busy} onClick={() => void load()}>Refresh memory</button>
      <button type="button" disabled={loading || busy} onClick={() => { setQuery(""); setPersonFilter(""); setTypeFilter("decision"); setSearch("note_type=decision"); if (search === "note_type=decision") void load(); }}>Show SENTRY decisions</button>
      <button type="button" disabled={loading || busy} onClick={() => { setQuery(""); setPersonFilter(""); setTypeFilter("learned_routine"); setSearch("note_type=learned_routine"); if (search === "note_type=learned_routine") void load(); }}>Show learned routines</button>
      <button type="button" disabled={!loaded || busy || Boolean(error)} onClick={() => { setEditing(null); setDraft(blank()); setFormOpen(true); setSelected(null); setNotice(""); }}>New note</button></div>
    <form className="form-grid" onSubmit={event => { event.preventDefault(); const params = new URLSearchParams();
      if (query.trim()) params.set("query", query.trim()); if (personFilter) params.set("person_id", personFilter); if (typeFilter) params.set("note_type", typeFilter);
      const next = params.toString(); setSearch(next); if (search === next) void load(); }}>
      <label>Search memory<input maxLength={120} value={query} onChange={event => setQuery(event.target.value)} /></label>
      <label>Filter memory by member<select value={personFilter} onChange={event => setPersonFilter(event.target.value)}><option value="">All members</option>{members.map(member => <option key={member.person_id} value={member.person_id}>{member.name}</option>)}</select></label>
      <label>Filter note type<select value={typeFilter} onChange={event => setTypeFilter(event.target.value)}><option value="">All note types</option>{["event", "profile", "preference", "routine", "lesson", "decision", "household_model", "observed_pattern", "hypothesis", "learned_routine", "rejected_hypothesis"].map(type => <option key={type}>{type.replaceAll("_", " ")}</option>)}</select></label>
      <button disabled={busy} type="submit">Search notes</button>
    </form>
    {error && <p className="notice error" role="alert">{error}{loaded && " Previously loaded notes may be out of date."}</p>}
    {notice && <p className="notice" role="status">{notice}</p>}
    {loading && <p className="muted" role="status">Reading memory…</p>}
    {loaded && !items.length && !error && <p className="muted">{search ? "No matching notes." : "No curated notes yet. Nothing has been seeded."}</p>}
    <ul className="clean-list list-spaced">{items.map(note => <li className="preference-row" key={note.note_id}><span><strong>{note.title ?? "Retracted note"}</strong><small className="muted">{note.classifier} · {label(note.classification)} · {note.enabled ? "Enabled" : "Disabled"}</small></span><button disabled={busy || loading} onClick={() => void open(note)}>Read {note.title ?? "note"}</button></li>)}</ul>
    {nextCursor && <button disabled={loading || busy} onClick={() => void load(nextCursor)}>More notes</button>}
    {search && truncated && <p className="muted">Showing bounded relevant matches. Narrow the query, member or note type for more specific results.</p>}
    {selected && !formOpen && <section aria-label="Selected memory note"><h3>{selected.title ?? label(selected.status)}</h3>
      <p className="knowledge-body">{selected.body ?? "This note no longer contains prose."}</p>
      <dl><dt>Classification</dt><dd>{label(selected.classification)}</dd><dt>Expires</dt><dd>{selected.expires_at ? new Date(selected.expires_at).toLocaleString() : "No automatic expiry"}</dd><dt>Observed at</dt><dd>{selected.observed_at ? new Date(selected.observed_at).toLocaleString() : "Not recorded"}</dd>
      <dt>Related people</dt><dd>{selected.person_refs?.length ? selected.person_refs.map(id => members.find(member => member.person_id === id)?.name ?? `Unresolved profile ${id}`).join(", ") : "No profile references"}</dd></dl>
      <p className="muted">Source references are attributed claims, not verified evidence or authority.</p>
      <ul>{selected.source_refs?.map((source, index) => <li key={index}>{source.kind}: {source.source_id} — {source.meaning}</li>)}</ul>
      {["decision", "household_model", "observed_pattern", "hypothesis", "learned_routine", "rejected_hypothesis"].includes(selected.note_type ?? "") && <p className="muted">This is a system-authored, evidence-linked record. It can be retracted, but not rewritten as though SENTRY reached a different conclusion.</p>}
      <div className="button-row">{selected.status === "ACTIVE" && <>{!["decision", "household_model", "observed_pattern", "hypothesis", "learned_routine", "rejected_hypothesis"].includes(selected.note_type ?? "") && <button disabled={busy} onClick={() => edit(selected)}>Edit note</button>}<button disabled={busy} onClick={() => {
        if (window.confirm("Retract this note? Its current prose and source explanations will be removed. Backups and past transcripts will not be erased.")) void write("retract", { note_id: selected.note_id, expected_digest: selected.digest });
      }}>Retract note</button></>}<button onClick={() => setSelected(null)}>Close note</button></div>
    </section>}
    {formOpen && <form className="stack" aria-label="Memory note editor" onSubmit={submit}>
      <h3>{editing ? "Correct note" : "Create note"}</h3><fieldset disabled={busy} className="stack"><legend>Evidence-backed note</legend>
      <label>Note title<input required maxLength={120} value={draft.title} onChange={event => update("title", event.target.value)} /></label>
      <label>Note text<textarea aria-label="Note text" required maxLength={4096} value={draft.body} onChange={event => update("body", event.target.value)} /></label>
      <div className="form-grid"><label>Note type<select value={draft.note_type} onChange={event => update("note_type", event.target.value)}>{["event", "profile", "preference", "routine", "lesson"].map(type => <option key={type}>{type}</option>)}</select></label>
      <label>Dewey class<select value={draft.classifier} onChange={event => update("classifier", event.target.value)}>{["000", "100", "300", "600", "640", "900", "920", ...(draft.classifier.includes(".") ? [draft.classifier] : [])].map(code => <option key={code}>{code}</option>)}</select></label>
      <label>Knowledge basis<select value={draft.classification} onChange={event => update("classification", event.target.value)}><option value="SENTRY_INFERENCE">Inference—not an owner assertion</option><option value="OBSERVATION">Attributed observation—not verified truth</option><option value="USER_STATED">User-stated claim—not verified truth</option><option value="DISCOVERED">Discovered claim—not verified truth</option></select></label>
      <label>Confidence<input required type="number" min="0" max="1" step="0.01" value={draft.confidence} onChange={event => update("confidence", event.target.value)} /></label>
      <label>Observed at (ISO with timezone)<input required={draft.classification === "OBSERVATION"} value={draft.observed_at} onChange={event => update("observed_at", event.target.value)} /></label>
      <label>Retention days (blank = no automatic expiry)<input type="number" min="1" max="36500" value={draft.retention_days} onChange={event => update("retention_days", event.target.value)} /></label></div>
      <fieldset><legend>Related household people (optional, up to 8)</legend>
        {!membersAvailable && <p className="muted">Member options unavailable. Existing references are preserved; Core validates membership before saving.</p>}
        {members.map(member => <label className="checkbox" key={member.person_id}><input type="checkbox" checked={draft.person_refs.includes(member.person_id)} disabled={!draft.person_refs.includes(member.person_id) && draft.person_refs.length >= 8}
          onChange={event => update("person_refs", event.target.checked ? [...draft.person_refs, member.person_id] : draft.person_refs.filter(id => id !== member.person_id))} />{member.name}</label>)}
        {draft.person_refs.filter(id => !members.some(member => member.person_id === id)).map(id => <label className="checkbox" key={id}><input type="checkbox" checked onChange={() => update("person_refs", draft.person_refs.filter(ref => ref !== id))} />Unresolved profile {id}</label>)}
      </fieldset>
      {draft.source_refs.map((source, index) => <fieldset key={index}><legend>Source {index + 1}</legend><div className="form-grid">
        <label>Source kind<select value={source.kind} onChange={event => update("source_refs", draft.source_refs.map((item, i) => i === index ? { ...item, kind: event.target.value } : item))}>{["event", "truth", "graph", "memory", "note", "request", "tool_result", "test", "external"].map(kind => <option key={kind}>{kind}</option>)}</select></label>
        <label>Source ID<input required maxLength={128} pattern="[A-Za-z0-9][A-Za-z0-9:._-]*" value={source.source_id} onChange={event => update("source_refs", draft.source_refs.map((item, i) => i === index ? { ...item, source_id: event.target.value } : item))} /></label></div>
        <label>What this source supports<input required maxLength={240} value={source.meaning} onChange={event => update("source_refs", draft.source_refs.map((item, i) => i === index ? { ...item, meaning: event.target.value } : item))} /></label>
        {draft.source_refs.length > 1 && <button type="button" onClick={() => update("source_refs", draft.source_refs.filter((_, i) => i !== index))}>Remove source {index + 1}</button>}
      </fieldset>)}
      <button type="button" disabled={draft.source_refs.length >= 12} onClick={() => update("source_refs", [...draft.source_refs, { kind: "event", source_id: "", meaning: "" }])}>Add source reference</button>
      <label className="checkbox"><input type="checkbox" checked={draft.enabled} onChange={event => update("enabled", event.target.checked)} />Note enabled</label>
      <p className="muted">Do not include secrets, restricted content, or raw transcripts. No automatic expiry keeps a note until corrected or retracted. Expired notes are hidden on reads; explicit purge removes current prose. Past transcripts and backups are unaffected.</p>
      <div className="button-row"><button type="submit">{editing ? "Save note correction" : "Save note"}</button><button type="button" onClick={() => { setFormOpen(false); setEditing(null); setDraft(blank()); }}>Cancel note</button></div></fieldset>
    </form>}
  </section>;
}
