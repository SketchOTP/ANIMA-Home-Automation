import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "./visuals";
import "./RingConnectionPanel.css";

type RingStatus = { configured: boolean; connected: boolean; state: "WAITING_HA_SETUP" | "HA_UNAVAILABLE" | "CONFIGURED" | "WAITING_RING_SETUP"; can_edit: boolean; can_setup: boolean; event_entities: number; video_access: false; connection_basis: "HA_TRANSPORT"; event_receipt_verified: boolean };
type SetupForm = { status: "FORM"; setup_id: string; step_id: "user" | "2fa"; fields: { name: string; type: string; required: true }[]; errors: { base?: "INVALID_AUTH" | "SETUP_FAILED" } };
type SetupResult = SetupForm | { status: "SUCCEEDED"; configured: true; refresh_required: true } | { status: "ABORTED"; reason: "ALREADY_CONFIGURED" | "SETUP_ABORTED" };
export type RingConnectionPanelProps = { csrfToken: string; onAuthFailure: () => void };
const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const uuid = (value: unknown): value is string => typeof value === "string" && /^[\da-f]{8}-(?:[\da-f]{4}-){3}[\da-f]{12}$/i.test(value);
function parseStatus(value: unknown): RingStatus {
  if (!object(value) || ![value.configured, value.connected, value.can_edit, value.can_setup, value.event_receipt_verified].every(item => typeof item === "boolean")
    || !["WAITING_HA_SETUP", "HA_UNAVAILABLE", "CONFIGURED", "WAITING_RING_SETUP"].includes(String(value.state))
    || typeof value.event_entities !== "number" || !Number.isSafeInteger(value.event_entities) || value.event_entities < 0
    || value.video_access !== false || value.connection_basis !== "HA_TRANSPORT") throw new Error("INVALID_RESPONSE");
  return value as unknown as RingStatus;
}
function parseSetup(value: unknown): SetupResult {
  if (!object(value)) throw new Error("INVALID_RESPONSE");
  if (value.status === "SUCCEEDED" && value.configured === true && value.refresh_required === true) return { status: "SUCCEEDED", configured: true, refresh_required: true };
  if (value.status === "ABORTED" && ["ALREADY_CONFIGURED", "SETUP_ABORTED"].includes(String(value.reason))) return { status: "ABORTED", reason: value.reason as "ALREADY_CONFIGURED" | "SETUP_ABORTED" };
  if (value.status !== "FORM" || !uuid(value.setup_id) || !["user", "2fa"].includes(String(value.step_id)) || !Array.isArray(value.fields) || !object(value.errors)) throw new Error("INVALID_RESPONSE");
  const expected = value.step_id === "user" ? [{ name: "username", type: "text" }, { name: "password", type: "password" }] : [{ name: "2fa", type: "password" }];
  if (value.fields.length !== expected.length || !expected.every(field => value.fields instanceof Array && value.fields.filter(actual => object(actual) && actual.name === field.name && actual.type === field.type && actual.required === true).length === 1)
    || Object.keys(value.errors).some(key => key !== "base") || !(value.errors.base === undefined || value.errors.base === "INVALID_AUTH" || value.errors.base === "SETUP_FAILED")) throw new Error("INVALID_RESPONSE");
  return { status: "FORM", setup_id: value.setup_id, step_id: value.step_id as "user" | "2fa", fields: expected.map(field => ({ ...field, required: true })), errors: { base: value.errors.base as SetupForm["errors"]["base"] } };
}

export function RingConnectionPanel({ csrfToken, onAuthFailure }: RingConnectionPanelProps) {
  const [status, setStatus] = useState<RingStatus | null>(null), [form, setForm] = useState<SetupForm | null>(null);
  const [username, setUsername] = useState(""), [password, setPassword] = useState(""), [code, setCode] = useState("");
  const [loading, setLoading] = useState(false), [busy, setBusy] = useState(false);
  const [error, setError] = useState(""), [notice, setNotice] = useState("");
  const auth = useRef(onAuthFailure); auth.current = onAuthFailure;
  const readAbort = useRef<AbortController | null>(null), writeAbort = useRef<AbortController | null>(null);
  const generation = useRef(0), mounted = useRef(true), locked = useRef(false);
  const formHeading = useRef<HTMLHeadingElement>(null);
  const clearCredentials = () => { setUsername(""); setPassword(""); setCode(""); };
  const deny = (statusCode: number) => { setStatus(null); setForm(null); clearCredentials(); setNotice(""); if (statusCode === 401) auth.current(); else setError("Only the authenticated household owner can set up Ring."); };
  const refresh = useCallback(async () => {
    readAbort.current?.abort(); const abort = new AbortController(); readAbort.current = abort;
    const current = ++generation.current; setLoading(true);
    let timeout = false;
    const timer = window.setTimeout(() => { timeout = true; abort.abort(); }, 10_000);
    try {
      const response = await fetch("/api/v1/ring/status", { credentials: "same-origin", cache: "no-store", signal: abort.signal, headers: { Accept: "application/json" } });
      if (current !== generation.current) return;
      if (response.status === 401 || response.status === 403) { deny(response.status); return; }
      if (!response.ok) throw new Error("UNAVAILABLE");
      const value = parseStatus(await response.json());
      if (current === generation.current && !abort.signal.aborted) setStatus(value);
    } catch {
      if (current === generation.current && (!abort.signal.aborted || timeout)) { setStatus(null); setError(timeout ? "Ring status timed out. Retry when Core is available." : "Ring status is unavailable. No connection is being assumed."); }
    } finally { window.clearTimeout(timer); if (current === generation.current) setLoading(false); }
  }, []);
  useEffect(() => { mounted.current = true; void refresh(); return () => { mounted.current = false; generation.current++; readAbort.current?.abort(); writeAbort.current?.abort(); }; }, [refresh]);
  useEffect(() => { if (form) formHeading.current?.focus(); }, [form]);
  const submit = async (start: boolean) => {
    if (locked.current || loading || !status?.can_edit || !status.can_setup || !csrfToken || !start && !form) return;
    const body = start ? {} : { setup_id: form!.setup_id, user_input: form!.step_id === "user" ? { username, password } : { "2fa": code } };
    // Secrets remain only in this explicit request; never use the generic
    // command mutation/outcome journal wrapper or persist form state.
    clearCredentials(); locked.current = true; setBusy(true); setError(""); setNotice("");
    const abort = new AbortController(); writeAbort.current = abort;
    const timer = window.setTimeout(() => abort.abort(), 20_000);
    try {
      const response = await fetch(`/api/v1/ring/setup/${start ? "start" : "continue"}`, { method: "POST", credentials: "same-origin", cache: "no-store", signal: abort.signal,
        headers: { "Content-Type": "application/json", Accept: "application/json", "X-Anima-CSRF": csrfToken }, body: JSON.stringify(body) });
      if (!mounted.current) return;
      if (response.status === 401 || response.status === 403) { deny(response.status); return; }
      if (!response.ok) throw new Error("SETUP_FAILED");
      const result = parseSetup(await response.json());
      if (!mounted.current || abort.signal.aborted) return;
      if (result.status === "FORM") {
        setForm(result);
        if (result.errors.base) setError(result.errors.base === "INVALID_AUTH" ? "Ring sign-in was not accepted. Check your credentials or code and submit again." : "Ring setup could not finish. Check the details and submit again.");
      } else {
        setForm(null);
        setNotice(result.status === "SUCCEEDED" ? "Ring setup accepted by Home Assistant. Refreshing status; cloud connectivity and event receipt are not yet verified." : result.reason === "ALREADY_CONFIGURED" ? "Home Assistant reports Ring is already configured. Refreshing status." : "Ring setup was stopped. Start again only when you are ready.");
        await refresh();
      }
    } catch {
      if (mounted.current) { setForm(null); setError("Ring setup was not confirmed. Refresh status before starting again. No credentials or codes will be retried automatically."); }
    } finally { window.clearTimeout(timer); locked.current = false; if (mounted.current) setBusy(false); }
  };
  const labels = { WAITING_HA_SETUP: "Home Assistant setup needed", HA_UNAVAILABLE: "Home Assistant unavailable", CONFIGURED: "Configured in Home Assistant", WAITING_RING_SETUP: "Ring setup needed" };
  return <section className="card ring-connection-panel" aria-labelledby="ring-panel-title">
    <header><div><h2 id="ring-panel-title"><Icon name="Notifications" />Ring notifications</h2><p className="muted">Doorbell and motion events through Home Assistant · No video access</p></div><button type="button" disabled={busy || loading} onClick={() => { setError(""); void refresh(); }}><Icon name="Refresh" />{loading ? "Refreshing Ring…" : "Refresh Ring status"}</button></header>
    {error && <p role="alert" className="notice error">{error}</p>}{notice && <p role="status" className="notice success">{notice}</p>}
    <div className="ring-readiness"><div><span>Setup</span><strong>{status ? labels[status.state] : "Status unavailable"}</strong></div><div><span>HA transport for Ring</span><strong>{status ? status.connected ? "Connected to Home Assistant" : "Not connected" : "Unknown"}</strong></div><div><span>Event entities</span><strong>{status ? status.event_entities : "—"}</strong></div><div><span>Event receipt</span><strong>{status?.event_receipt_verified ? "Reported as verified by Core" : "Not verified"}</strong></div></div>
    <p className="muted">HA transport connectivity does not verify Ring cloud connectivity, live event delivery, notification delivery, or who is at the door.</p>
    {status && !status.can_edit && <p className="muted">Only the household owner can configure Ring.</p>}
    {status?.state === "WAITING_HA_SETUP" && <p>Connect Home Assistant first using the existing integration controls.</p>}
    {status?.state === "HA_UNAVAILABLE" && <p>Restore the Home Assistant connection, then refresh this status.</p>}
    {!form && status?.can_edit && status.can_setup && <button type="button" disabled={busy || loading || !csrfToken} onClick={() => void submit(true)}>{busy ? "Starting Ring setup…" : "Set up Ring"}</button>}
    {form && <form autoComplete="off" className="ring-setup-form" onSubmit={event => { event.preventDefault(); void submit(false); }}>
      <h3 ref={formHeading} tabIndex={-1}>{form.step_id === "user" ? "Ring account sign-in" : "Ring two-factor verification"}</h3><p className="muted">Sent only to the local Core setup route. Passwords and codes are cleared on submit; no chat or household journal command is created.</p>
      <fieldset disabled={busy || loading || !status?.can_edit || !status.can_setup}><legend>{form.step_id === "user" ? "Ring credentials" : "Verification code"}</legend>
        {form.step_id === "user" ? <><label htmlFor="ring-username">Ring username</label><input id="ring-username" required type="text" autoComplete="off" autoCapitalize="none" spellCheck={false} maxLength={320} value={username} onChange={event => setUsername(event.target.value)} /><label htmlFor="ring-password">Ring password</label><input id="ring-password" required type="password" autoComplete="new-password" maxLength={1024} value={password} onChange={event => setPassword(event.target.value)} /></> : <><label htmlFor="ring-code">Ring verification code</label><input id="ring-code" required type="password" autoComplete="off" autoCapitalize="none" spellCheck={false} maxLength={128} value={code} onChange={event => setCode(event.target.value)} /></>}
        <div className="button-row"><button type="submit">{busy ? "Submitting…" : form.step_id === "user" ? "Continue Ring sign-in" : "Verify Ring code"}</button><button type="button" onClick={() => { setForm(null); clearCredentials(); setError(""); }}>Close setup form</button></div>
      </fieldset>
    </form>}
  </section>;
}
