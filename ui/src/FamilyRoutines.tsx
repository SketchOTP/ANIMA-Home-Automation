import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "./visuals";
import "./FamilyRoutines.css";

type Routine = {
  routine_id: string; version: string; person_id: string; person_name: string;
  label: string; days: number[]; start: string; end: string; timezone: string;
  place_id: string | null; place_name: string | null; notes: string; enabled: boolean;
  created_at: string; provenance: { kind: string }; classification: string; authority: string;
};
type Draft = Pick<Routine, "person_id" | "label" | "days" | "start" | "end" | "timezone" | "place_id" | "notes" | "enabled">;
type Page = { items: Routine[]; next_cursor: string | null; members: { person_id: string; name: string }[]; places: { place_id: string; name: string }[]; can_edit: boolean };
type Outcome = { status: string };
type Props = {
  mutate: (path: string, payload?: Record<string, unknown>) => Promise<Outcome | null>;
  onAuthFailure: () => void;
  openUsers: () => void;
};
const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const blank = (): Draft => ({ person_id: "", label: "", days: [], start: "", end: "", timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC", place_id: null, notes: "", enabled: true });
const fields = (routine: Routine): Draft => ({ person_id: routine.person_id, label: routine.label, days: [...routine.days], start: routine.start, end: routine.end, timezone: routine.timezone, place_id: routine.place_id, notes: routine.notes, enabled: routine.enabled });
const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === "string" && value.length > 0;
const time = (value: unknown): value is string => typeof value === "string" && /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value);
function parsePage(value: unknown): Page {
  if (!object(value) || !Array.isArray(value.items) || !Array.isArray(value.members) || !Array.isArray(value.places)
    || typeof value.can_edit !== "boolean" || !(value.next_cursor === null || text(value.next_cursor))
    || !value.members.every(person => object(person) && text(person.person_id) && text(person.name))
    || !value.places.every(place => object(place) && text(place.place_id) && text(place.name))
    || !value.items.every(item => object(item) && text(item.routine_id) && text(item.version)
      && text(item.person_id) && text(item.person_name) && text(item.label)
      && Array.isArray(item.days) && item.days.length > 0 && item.days.length <= 7
      && item.days.every(day => Number.isInteger(day) && day >= 0 && day <= 6) && new Set(item.days).size === item.days.length
      && time(item.start) && time(item.end) && item.start !== item.end && text(item.timezone)
      && (item.place_id === null || text(item.place_id)) && (item.place_name === null || text(item.place_name))
      && typeof item.notes === "string" && typeof item.enabled === "boolean"
      && text(item.created_at) && Number.isFinite(Date.parse(item.created_at))
      && object(item.provenance) && item.provenance.kind === "EXPLICIT_INPUT"
      && item.classification === "OWNER_DECLARED_EXPECTATION" && item.authority === "NONE")) {
    throw new Error("INVALID_ROUTINE_PAGE");
  }
  if (new Set(value.items.map(item => item.routine_id)).size !== value.items.length) throw new Error("INVALID_ROUTINE_PAGE");
  return value as Page;
}

export function FamilyRoutines({ mutate, onAuthFailure, openUsers }: Props) {
  const [page, setPage] = useState<Page | null>(null);
  const [draft, setDraft] = useState<Draft>(blank);
  const [editing, setEditing] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [personFilter, setPersonFilter] = useState("");
  const [reviewRequired, setReviewRequired] = useState(false);
  const [removing, setRemoving] = useState<Routine | null>(null);
  const editorHeading = useRef<HTMLHeadingElement>(null);
  const removalHeading = useRef<HTMLHeadingElement>(null);
  const mutationLock = useRef(false);
  const mounted = useRef(true);
  const authFailure = useRef(onAuthFailure); authFailure.current = onAuthFailure;
  const generation = useRef(0);
  const pending = useRef<AbortController | null>(null);
  const expired = useRef(false);
  const reload = useCallback(async (cursor: string | null = null, person = personFilter) => {
    pending.current?.abort();
    const controller = new AbortController(); pending.current = controller;
    const current = ++generation.current; setLoading(true); setError("");
    let timedOut = false;
    const timer = window.setTimeout(() => { timedOut = true; controller.abort(); }, 10_000);
    try {
      const query = new URLSearchParams({ limit: "50" });
      if (cursor) query.set("cursor", cursor);
      if (person) query.set("person_id", person);
      const response = await fetch(`/api/v1/family-routines?${query}`, { credentials: "same-origin", cache: "no-store", signal: controller.signal, headers: { Accept: "application/json" } });
      if (current !== generation.current) return;
      if (response.status === 401 || response.status === 403) {
        setPage(null); setDraft(blank()); setEditing(null); setRemoving(null); setNotice(""); setReviewRequired(false);
        if (response.status === 401) { expired.current = true; authFailure.current(); }
        else setError("You no longer have access to family routines. Ask the household owner to check access.");
        return;
      }
      if (!response.ok) throw new Error("ROUTINES_UNAVAILABLE");
      const value = parsePage(await response.json());
      if (current === generation.current && !expired.current && !controller.signal.aborted) {
        setPage(previous => ({ ...value, items: cursor && previous ? [...new Map([...previous.items, ...value.items].map(item => [item.routine_id, item])).values()] : value.items }));
        return true;
      }
    } catch (reason) {
      if (current === generation.current && (!controller.signal.aborted || timedOut)) {
        setPage(null); setRemoving(null);
        setError(timedOut ? "Loading routines timed out. Your draft is kept; retry loading when Core is connected." : reason instanceof Error && reason.message === "INVALID_ROUTINE_PAGE" ? "Core returned an invalid routines response. Your draft is kept; retry loading." : "Family routines could not be loaded. Your draft is kept; retry when Core is connected.");
      }
    } finally { window.clearTimeout(timer); if (current === generation.current) setLoading(false); }
  }, [personFilter]);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => { if (removing) removalHeading.current?.focus(); }, [removing]);
  useEffect(() => { void reload(); return () => { generation.current++; pending.current?.abort(); }; }, [reload]);
  const update = <K extends keyof Draft,>(key: K, value: Draft[K]) => setDraft(previous => ({ ...previous, [key]: value }));
  const cancel = () => { setEditing(null); setDraft(blank()); setReviewRequired(false); setError(""); };
  const edit = (routine: Routine) => { setEditing(routine.routine_id); setDraft(fields(routine)); setNotice(""); setError(""); setReviewRequired(false); setRemoving(null); editorHeading.current?.focus(); };
  const change = async (operation: string, payload: Record<string, unknown>, success: string, resetDraft: boolean) => {
    if (mutationLock.current || expired.current || !page?.can_edit || loading) return;
    mutationLock.current = true; setBusy(true); setError(""); setNotice("");
    let succeeded = false;
    try {
      const result = await mutate(`/api/v1/family-routines/${operation}`, payload);
      if (!mounted.current || expired.current) return;
      succeeded = result?.status === "SUCCEEDED";
      setRemoving(null);
      if (succeeded) {
        if (resetDraft) cancel();
        setNotice(success); setRemoving(null);
      } else setReviewRequired(true);
      const refreshed = await reload();
      if (!succeeded && refreshed && mounted.current && !expired.current) setError("Change not confirmed. Draft kept; the saved list was refreshed. Review the current version before another change. No automatic retry was sent.");
    } catch {
      if (mounted.current && !expired.current) {
        setReviewRequired(true); const refreshed = await reload();
        if (refreshed && mounted.current && !expired.current) setError("Change not confirmed. Draft kept. Review saved routines before trying again; no automatic retry was sent.");
      }
    } finally { mutationLock.current = false; if (mounted.current) setBusy(false); }
  };
  const save = async (event: React.FormEvent) => {
    event.preventDefault(); if (busy || expired.current || reviewRequired) return;
    if (!draft.days.length || draft.start === draft.end) { setError("Select at least one day and different start and end times."); return; }
    await change(editing ? "update" : "create", { ...draft, ...(editing ? { routine_id: editing } : {}) }, editing ? "Routine updated. Previous version retained." : "Routine saved.", true);
  };
  return <div className="dashboard family-routines">
    <section className="card"><h2 ref={editorHeading} tabIndex={-1}><Icon name="Calendar" /> {editing ? "Edit family routine" : "Add family routine"}</h2>
      <p className="muted">Create an owner-declared schedule or expectation for an existing household member. These records give SENTRY context; they do not prove presence, authenticate anyone, schedule an action, or execute an automation.</p>
      <button type="button" onClick={openUsers}>Manage household users</button>
      {error && <p role="alert" className="notice error">{error}</p>}
      {error && personFilter && <button type="button" disabled={busy || loading} onClick={() => setPersonFilter("")}>Reset member filter</button>}
      {notice && <p role="status">{notice}</p>}
      {reviewRequired && <div className="notice warning"><p>Your draft is retained. Choose Edit on a current saved routine to review it, or check that a new routine was not already saved before discarding this draft.</p><button type="button" disabled={busy || loading} onClick={cancel}>Discard draft and start new</button></div>}
      {!page && <button type="button" disabled={loading} onClick={() => void reload()}>{loading ? "Loading routines…" : "Retry routines"}</button>}
      {page && !page.members.length && <p className="empty-state">No household members are available. Add a person on Users, then return here to create a routine.</p>}
      {page && !page.can_edit && <p className="muted">Only the authenticated household owner can change routines.</p>}
      <form className="stack" onSubmit={event => void save(event)}>
        <fieldset disabled={!page?.can_edit || !page.members.length || busy || loading}><legend>Routine details</legend>
          <label>Household member<select required value={draft.person_id} onChange={event => update("person_id", event.target.value)}><option value="">Select a member</option>{page?.members.map(person => <option key={person.person_id} value={person.person_id}>{person.name}</option>)}</select></label>
          <label>Routine label<input required maxLength={120} value={draft.label} onChange={event => update("label", event.target.value)} /></label>
          <fieldset><legend>Days — local start day</legend><div className="button-row"><button type="button" onClick={() => update("days", [0, 1, 2, 3, 4])}>Weekdays</button><button type="button" onClick={() => update("days", [5, 6])}>Weekends</button><button type="button" onClick={() => update("days", [0, 1, 2, 3, 4, 5, 6])}>Every day</button></div><div className="button-row">{days.map((day, index) => <label key={day} className="checkbox"><input type="checkbox" checked={draft.days.includes(index)} onChange={() => update("days", draft.days.includes(index) ? draft.days.filter(value => value !== index) : [...draft.days, index].sort())} />{day.slice(0, 3)}</label>)}</div></fieldset>
          <div className="settings-form"><label>Start time<input required type="time" value={draft.start} onChange={event => update("start", event.target.value)} /></label><label>End time<input required type="time" value={draft.end} onChange={event => update("end", event.target.value)} /></label></div>
          <label>IANA time zone<input required maxLength={64} placeholder="America/New_York" value={draft.timezone} onChange={event => update("timezone", event.target.value)} /></label>
          <p className="muted">Starts with this browser’s time zone. Check it matches the member’s routine; Core validates the zone when saving.</p>
          <p className="muted">An end earlier than the start finishes the next day. Times remain local to this time zone.</p>
          <label>Room or zone (optional)<select value={draft.place_id ?? ""} onChange={event => update("place_id", event.target.value || null)}><option value="">No specific place</option>{page?.places.map(place => <option key={place.place_id} value={place.place_id}>{place.name}</option>)}</select></label>
          <label htmlFor="family-routine-notes">Description</label><textarea id="family-routine-notes" maxLength={1000} value={draft.notes} onChange={event => update("notes", event.target.value)} />
          <label className="checkbox"><input type="checkbox" checked={draft.enabled} onChange={event => update("enabled", event.target.checked)} />Enabled expectation</label>
          <div className="button-row"><button type="submit" disabled={reviewRequired}>{busy ? "Saving…" : editing ? "Save routine changes" : "Save routine"}</button>{editing && <button type="button" onClick={cancel}>Cancel edit</button>}</div>
        </fieldset>
      </form>
    </section>
    <section className="card" aria-busy={loading || busy}><h2>Saved family routines</h2><p className="muted">Review routines by member, edit their schedule or description, disable them without deleting history, or remove them from active context. Saved changes are versioned and survive restarts.</p><button type="button" disabled={loading || busy} onClick={() => void reload()}>Refresh routines</button>
      {page && <label>Filter routines by member<select disabled={busy || loading} value={personFilter} onChange={event => { setPersonFilter(event.target.value); setPage(previous => previous ? { ...previous, items: [], next_cursor: null } : null); setRemoving(null); }}><option value="">All household members</option>{page.members.map(person => <option key={person.person_id} value={person.person_id}>{person.name}</option>)}</select></label>}
      {loading && <p role="status">Loading saved routines…</p>}
      {page && !loading && !page.items.length && <p className="empty-state">{personFilter ? "No routines saved for this member." : "No family routines saved. Nothing is inferred or prefilled."}</p>}
      {removing && <section role="group" aria-label="Confirm routine removal" className="notice warning"><h3 ref={removalHeading} tabIndex={-1}>Remove {removing.label}?</h3><p>This retracts the saved expectation from the active list. Its history is retained; this is not permanent deletion.</p><div className="button-row"><button type="button" disabled={busy || loading} onClick={() => void change("retract", { routine_id: removing.routine_id }, "Routine removed from the active list. History retained.", editing === removing.routine_id)}>Confirm removal</button><button type="button" disabled={busy} onClick={() => setRemoving(null)}>Keep routine</button></div></section>}
      <ul className="clean-list list-spaced">{page?.items.map(routine => <li className="preference-row" key={routine.routine_id}>
        <div><strong>{routine.label}</strong><p>{routine.person_name} · {routine.enabled ? "Enabled" : "Disabled"}</p><p>{routine.days.map(day => days[day].slice(0, 3)).join(" · ")} · {routine.start}–{routine.end}{routine.end < routine.start ? " (+1 day)" : ""} · {routine.timezone}</p>{routine.place_name && <p>{routine.place_name}</p>}{routine.notes && <p>{routine.notes}</p>}<small className="muted">Owner declared · {routine.provenance.kind} · saved {new Date(routine.created_at).toLocaleString()}</small><details><summary>Version &amp; provenance</summary><p className="muted" style={{ overflowWrap: "anywhere" }}>Version: {routine.version}<br />{routine.classification} · Authority: {routine.authority}</p></details></div>
        {page.can_edit && <span className="button-row"><button type="button" disabled={busy || loading} onClick={() => edit(routine)} aria-label={`Edit ${routine.label}`}>Edit</button><button type="button" disabled={busy || loading} onClick={() => void change(routine.enabled ? "disable" : "update", routine.enabled ? { routine_id: routine.routine_id } : { ...fields(routine), routine_id: routine.routine_id, enabled: true }, routine.enabled ? "Routine disabled. History retained." : "Routine enabled. Previous version retained.", editing === routine.routine_id)} aria-label={`${routine.enabled ? "Disable" : "Enable"} ${routine.label}`}>{routine.enabled ? "Disable" : "Enable"}</button><button type="button" disabled={busy || loading} onClick={() => setRemoving(routine)} aria-label={`Remove ${routine.label}`}>Remove</button></span>}
      </li>)}</ul>
      {page?.next_cursor && <button type="button" disabled={loading || busy} onClick={() => void reload(page.next_cursor)}>Load more routines</button>}
    </section>
  </div>;
}
