import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "./visuals";
import "./PreferencesPanel.css";

const categories = ["general", "notifications", "routines", "alerts", "comfort", "meals", "shopping", "privacy", "other"] as const;
type Category = typeof categories[number];
type Scope = "household" | "personal";
type Member = { person_id: string; name: string };
type Preference = {
  preference_id: string; version: string; scope: Scope; person_id: string | null;
  content: string; category: Category; created_at: string; provenance: { kind: string };
};
type PreferencePage = { items: Preference[]; members: Member[]; can_edit: boolean; next_cursor: string | null };
type Draft = Pick<Preference, "scope" | "person_id" | "content" | "category">;
type Outcome = { status: string; result?: unknown };
export type PreferencesPanelProps = {
  mutate: (path: string, payload?: Record<string, unknown>) => Promise<Outcome | null>;
  onAuthFailure: () => void;
};
const blank = (): Draft => ({ scope: "household", person_id: null, content: "", category: "general" });
const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const nonempty = (value: unknown): value is string => typeof value === "string" && value.length > 0;
function parsePage(value: unknown): PreferencePage {
  if (!object(value) || !Array.isArray(value.items) || !Array.isArray(value.members) || typeof value.can_edit !== "boolean"
    || !(value.next_cursor == null || nonempty(value.next_cursor))
    || !value.members.every(member => object(member) && nonempty(member.person_id) && nonempty(member.name))) throw new Error("INVALID_PAGE");
  const items = value.items.map((item): Preference => {
    if (!object(item) || !nonempty(item.preference_id) || !nonempty(item.content) || typeof item.category !== "string"
      || !categories.includes(item.category as Category) || !nonempty(item.created_at) || !Number.isFinite(Date.parse(item.created_at))
      || !object(item.provenance) || item.provenance.kind !== "EXPLICIT_INPUT"
      || !(item.scope === "household" && item.person_id === null || item.scope === "personal" && nonempty(item.person_id))
      || !(item.version == null || nonempty(item.version))) throw new Error("INVALID_PAGE");
    return { preference_id: item.preference_id, version: item.version as string ?? item.preference_id, scope: item.scope as Scope,
      person_id: item.person_id as string | null, content: item.content, category: item.category as Category,
      created_at: item.created_at, provenance: { kind: item.provenance.kind } };
  });
  if (new Set(items.map(item => item.preference_id)).size !== items.length) throw new Error("INVALID_PAGE");
  return { items, members: value.members.map(member => ({ person_id: member.person_id, name: member.name })), can_edit: value.can_edit, next_cursor: value.next_cursor as string ?? null };
}

export function PreferencesPanel({ mutate, onAuthFailure }: PreferencesPanelProps) {
  const [page, setPage] = useState<PreferencePage | null>(null);
  const [draft, setDraft] = useState<Draft>(blank);
  const [editing, setEditing] = useState<Preference | null>(null);
  const [removing, setRemoving] = useState<Preference | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [reviewRequired, setReviewRequired] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const heading = useRef<HTMLHeadingElement>(null);
  const confirmation = useRef<HTMLHeadingElement>(null);
  const controller = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const mounted = useRef(true);
  const locked = useRef(false);
  const authFailure = useRef(onAuthFailure); authFailure.current = onAuthFailure;
  const clearDraft = () => { setDraft(blank()); setEditing(null); setReviewRequired(false); };
  const reload = useCallback(async (cursor: string | null = null) => {
    controller.current?.abort(); const abort = new AbortController(); controller.current = abort;
    const current = ++generation.current; setLoading(true); setError("");
    let timedOut = false;
    const timeout = window.setTimeout(() => { timedOut = true; abort.abort(); }, 10_000);
    try {
      const query = new URLSearchParams({ limit: "50" });
      if (cursor) query.set("cursor", cursor);
      if (filter === "household" || filter === "personal") query.set("scope", filter);
      else if (filter !== "all") { query.set("scope", "personal"); query.set("person_id", filter); }
      if (categoryFilter !== "all") query.set("category", categoryFilter);
      const response = await fetch(`/api/v1/preferences?${query}`, { credentials: "same-origin", cache: "no-store", signal: abort.signal, headers: { Accept: "application/json" } });
      if (current !== generation.current) return false;
      if (response.status === 401 || response.status === 403) {
        setPage(null); clearDraft(); setRemoving(null); setNotice(""); setSearch(""); setFilter("all"); setCategoryFilter("all");
        if (response.status === 401) authFailure.current();
        else setError("You no longer have access to these preferences. Ask the household owner to check access.");
        return false;
      }
      if (!response.ok) throw new Error("UNAVAILABLE");
      const next = parsePage(await response.json());
      if (current !== generation.current || abort.signal.aborted) return false;
      setPage(previous => ({ ...next, items: cursor && previous ? [...new Map([...previous.items, ...next.items].map(item => [item.preference_id, item])).values()] : next.items }));
      return true;
    } catch (reason) {
      if (current === generation.current && (!abort.signal.aborted || timedOut)) {
        setPage(null); setRemoving(null);
        setError(timedOut ? "Loading preferences timed out. Draft kept; retry loading when Core is connected." : reason instanceof Error && reason.message === "INVALID_PAGE" ? "Core returned an invalid preferences response. Draft kept; retry loading." : "Preferences could not be loaded. Draft kept; retry when Core is connected.");
      }
      return false;
    } finally { window.clearTimeout(timeout); if (current === generation.current) setLoading(false); }
  }, [filter, categoryFilter]);
  useEffect(() => { mounted.current = true; void reload(); return () => { mounted.current = false; generation.current++; controller.current?.abort(); }; }, [reload]);
  useEffect(() => { if (removing) confirmation.current?.focus(); }, [removing]);
  const edit = (item: Preference) => {
    setEditing(item); setDraft({ scope: item.scope, person_id: item.person_id, content: item.content, category: item.category });
    setReviewRequired(false); setRemoving(null); setNotice(""); setError(""); heading.current?.focus();
  };
  const change = async (operation: "create" | "update" | "retract", payload: Record<string, unknown>) => {
    if (locked.current || loading || !page?.can_edit) return;
    locked.current = true; setBusy(true); setError(""); setNotice("");
    try {
      const result = await mutate(`/api/v1/preferences/${operation}`, payload);
      if (!mounted.current) return;
      setRemoving(null);
      const success = result?.status === "SUCCEEDED" && (!object(result.result) || !result.result.status || result.result.status === "SUCCEEDED");
      if (success) {
        if (operation !== "retract" || editing?.preference_id === payload.preference_id) clearDraft();
        setNotice(operation === "retract" ? "Preference removed from active context. History retained." : operation === "update" ? "Preference corrected. Previous version retained." : "Preference saved as context, not an action or permission.");
      } else setReviewRequired(true);
      const refreshed = await reload();
      if (!success && refreshed && mounted.current) setError("Change not confirmed. Draft kept; review the refreshed saved preferences before another change. No automatic retry was sent.");
    } catch {
      if (mounted.current) {
        setReviewRequired(true); const refreshed = await reload();
        if (refreshed && mounted.current) setError("Change not confirmed. Draft kept; review saved preferences before trying again. No automatic retry was sent.");
      }
    } finally { locked.current = false; if (mounted.current) setBusy(false); }
  };
  const memberName = (id: string | null) => page?.members.find(member => member.person_id === id)?.name ?? "Member unavailable";
  const items = page?.items.filter(item => (filter === "all" || filter === "household" && item.scope === "household" || filter === "personal" && item.scope === "personal" || item.scope === "personal" && item.person_id === filter)
    && (categoryFilter === "all" || item.category === categoryFilter)
    && item.content.toLocaleLowerCase().includes(search.toLocaleLowerCase())) ?? [];
  const canSave = Boolean(page?.can_edit && !busy && !loading && !reviewRequired && draft.content.trim()
    && (draft.scope === "household" || page.members.some(member => member.person_id === draft.person_id)));
  return <div className="dashboard preferences-panel">
    <section className="card">
      <div className="card-heading"><h2 ref={heading} tabIndex={-1}><Icon name="Preferences" />{editing ? "Correct a preference" : "Add a preference"}</h2></div>
      <p className="muted">Describe a shared household choice or a person’s preference in your own words. This is context, not a command, automation, or permission.</p>
      {error && <p role="alert" className="notice error">{error}</p>}
      {error && (filter !== "all" || categoryFilter !== "all") && <button type="button" disabled={busy || loading} onClick={() => { setFilter("all"); setCategoryFilter("all"); }}>Reset preference filters</button>}
      {notice && <p role="status" className="notice success">{notice}</p>}
      {!page && <button type="button" disabled={loading} onClick={() => void reload()}>{loading ? "Loading preferences…" : "Retry preferences"}</button>}
      {page && !page.can_edit && <p className="muted">Only the authenticated household owner can change these preferences.</p>}
      {reviewRequired && <div className="notice warning"><p>Review a current saved preference before editing again, or check whether your new preference was saved before discarding this draft.</p><button type="button" disabled={busy || loading} onClick={() => { clearDraft(); setError(""); }}>Discard draft and start new</button></div>}
      <form className="stack" onSubmit={event => { event.preventDefault(); if (canSave) void change(editing ? "update" : "create", { content: draft.content, category: draft.category, person_id: draft.person_id, ...(editing ? { preference_id: editing.preference_id } : {}) }); }}>
        <fieldset disabled={!page?.can_edit || busy || loading}><legend>Preference details</legend>
          <label>Applies to<select value={draft.scope} onChange={event => setDraft(previous => ({ ...previous, scope: event.target.value as Scope, person_id: null }))}><option value="household">Shared household</option><option value="personal">One person</option></select></label>
          {draft.scope === "personal" && <><label>Household member<select required value={draft.person_id ?? ""} onChange={event => setDraft(previous => ({ ...previous, person_id: event.target.value || null }))}><option value="">Select a member</option>{page?.members.map(member => <option key={member.person_id} value={member.person_id}>{member.name}</option>)}</select></label>{!page?.members.length && <p className="muted">Add a canonical household member in Routines first. No person is assumed.</p>}</>}
          <label>Preference<textarea required maxLength={1000} value={draft.content} onChange={event => setDraft(previous => ({ ...previous, content: event.target.value }))} placeholder="Describe the preference in your own words" aria-describedby="preference-text-help" /></label>
          <small id="preference-text-help" className="muted">Free text · {draft.content.length}/1000 characters · Nothing here executes a device action.</small>
          <label>Category<select value={draft.category} onChange={event => setDraft(previous => ({ ...previous, category: event.target.value as Category }))}>{categories.map(category => <option key={category} value={category}>{category[0].toUpperCase() + category.slice(1)}</option>)}</select></label>
          <div className="button-row"><button type="submit" disabled={!canSave}>{busy ? "Saving…" : editing ? "Save correction" : "Save preference"}</button>{editing && <button type="button" onClick={() => { clearDraft(); setError(""); }}>Cancel correction</button>}</div>
        </fieldset>
      </form>
    </section>
    <section className="card" aria-busy={loading || busy}>
      <div className="card-heading"><h2><Icon name="Home" />Saved preferences</h2><button type="button" disabled={loading || busy} onClick={() => void reload()}><Icon name="Refresh" />Refresh preferences</button></div>
      <div className="filter-bar"><label>Filter preferences<select disabled={busy} value={filter} onChange={event => setFilter(event.target.value)}><option value="all">All scopes</option><option value="household">Shared household</option><option value="personal">All personal preferences</option>{page?.members.map(member => <option key={member.person_id} value={member.person_id}>{member.name}</option>)}</select></label><label>Filter category<select disabled={busy} value={categoryFilter} onChange={event => setCategoryFilter(event.target.value)}><option value="all">All categories</option>{categories.map(category => <option key={category} value={category}>{category}</option>)}</select></label><label>Search preference text<input type="search" value={search} onChange={event => setSearch(event.target.value)} /></label></div>
      {loading && <p role="status">Loading saved preferences…</p>}
      {removing && <section className="notice warning" role="group" aria-label="Confirm preference removal"><h3 ref={confirmation} tabIndex={-1}>Remove this preference?</h3><p className="preference-text">{removing.content}</p><p>Remove it from active context. Retraction retains history; it does not permanently erase records or undo device actions.</p><div className="button-row"><button type="button" disabled={busy || loading} onClick={() => void change("retract", { preference_id: removing.preference_id })}>Confirm removal</button><button type="button" disabled={busy} onClick={() => setRemoving(null)}>Keep preference</button></div></section>}
      {page && <p className="muted">{items.length} shown · {page.items.length} loaded{page.next_cursor ? " · More preferences available; text search applies to loaded items." : ""}</p>}
      {page && !loading && !items.length && <p className="empty-state">{page.items.length ? "No loaded preferences match these filters." : "No explicit preferences saved. Nothing has been inferred or prefilled."}</p>}
      <ul className="clean-list preference-cards">{items.map(item => <li key={item.preference_id}>
        <span className="preference-scope"><Icon name={item.scope === "household" ? "Home" : "Person"} />{item.scope === "household" ? "Shared household" : memberName(item.person_id)}</span>
        <p className="preference-text">{item.content}</p><small className="muted">{item.category} · Saved {new Date(item.created_at).toLocaleString()}</small>
        <details><summary>Version &amp; provenance</summary><p className="muted">{item.provenance.kind} · Explicit preference · Context only<br />Version: {item.version}</p></details>
        {page?.can_edit && <div className="button-row"><button type="button" disabled={busy || loading} onClick={() => edit(item)}>Edit preference</button><button type="button" disabled={busy || loading} onClick={() => setRemoving(item)}>Remove preference</button></div>}
      </li>)}</ul>
      {page?.next_cursor && <button type="button" disabled={loading || busy} onClick={() => void reload(page.next_cursor)}>Load more preferences</button>}
    </section>
  </div>;
}
