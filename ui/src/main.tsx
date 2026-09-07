import { StrictMode, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { PreferencesPanel } from "./PreferencesPanel";
import { Icon, StatusRing, Meter } from "./visuals";
import { KnowledgePanel } from "./KnowledgePanel";
import { FamilyRoutines } from "./FamilyRoutines";
import { HouseholdPresencePanel } from "./HouseholdPresencePanel";
import { VendorConnectionsPanel } from "./VendorConnectionsPanel";
import { InitiativePanel } from "./InitiativePanel";
import { RingConnectionPanel } from "./RingConnectionPanel";
import { UsersPanel } from "./UsersPanel";

type Status = "CURRENT" | "STALE" | "UNKNOWN" | "UNAVAILABLE" | "CONFLICTING";
type Settings = {
  version: number; appearance: "system" | "light" | "night"; accent: "ember" | "sage" | "sky" | "purple";
  density: "comfortable" | "compact"; reduced_motion: boolean; text_scale: "small" | "normal" | "large";
  display_mode: "wall" | "tablet" | "phone" | "desktop"; visible_widgets: string[]; widget_order: string[];
};
type SentryVoiceSettings = { voice_id: string; speech_speed: number; sleep_enabled: boolean };
type Bootstrap = { identity: { display_name: string; assurance: string }; household: { name: string }; theme: Pick<Settings, "appearance" | "accent" | "density" | "reduced_motion" | "text_scale">; layout: Pick<Settings, "display_mode" | "visible_widgets" | "widget_order">; csrf_token: string };
type Task = { task_id: string; title: string; status: string; next_run_at?: string };
type CalendarEvent = { event_id: string; title: string; start_at: string; end_at: string; status: string; version?: number };
type Device = { device_id: string; name: string; kind: string; state: string };
type Room = { place_id: string; name: string; kind: string; devices: Device[] };
type Space = { place_id: string; name: string; kind: string; parent_id?: string | null };
type LastReportedState = { last_reported_state?: string; last_reported_at?: string; last_reported_source?: string };
type DeviceCapability = LastReportedState & { type: string; label: string; readable: boolean; writable: boolean; state: string; truth_status: string; observed_at?: string | null };
type ProviderDevice = LastReportedState & { external_object_kind: string; device_handle: string; canonical_name?: string; present: boolean; state?: string; truth_status?: string; observed_at?: string | null; capabilities?: DeviceCapability[]; metadata: Record<string, string | null> };
type AlertPolicy = { policy_id: string; resource_ids: string[]; event_type: string; timezone: string; start_local: string; end_local: string; priority: number; guaranteed_attention: boolean; delivery_mode: "SENTRY_COGNITION" | "NOTIFICATION"; enabled: boolean; version: number };
type AlertEvent = { alert_id: string; source_event_id?: string | null; resource_id: string; resource_name: string; event_type: string; occurred_at: string; priority: number; delivery_mode: string; delivery_status: string };
type Page<T> = { items: T[]; next_cursor: string | null };
type NotificationRoute = { route_id: string; label: string; enabled: boolean; minimum_priority: number; version: number; provider: string; destination: string };
type BackupRecord = { backup_id: string; captured_at: string; size_bytes: number; sha256: string; schema_version: string; restorable: boolean };
type SceneStep = { resource_id: string; desired_on: boolean };
type Scene = { scene_id: string; name: string; steps: SceneStep[]; enabled: boolean; version: number; updated_at: string };
type Automation = { automation_id: string; name: string; trigger_resource_id: string; trigger_state: "on" | "off"; action_resource_id: string; action_desired_on: boolean; enabled: boolean; version: number; updated_at: string };
type Home = { household: { name: string; status: Status; summary: string }; security: { status: Status; label: string }; presence: { people: { name: string; state: string }[] }; weather: { status: Status; summary: string }; calendar: CalendarEvent[]; tasks: Task[]; controls: { control_id: string; label: string; state: string; capability?: string }[]; activity: { summary: string; status: Status }[]; voice: { status: Status; label: string }; rooms: Room[]; notifications: { notification_id: string; summary: string; status: Status; importance?: string; occurred_at?: string }[]; reports: { report_id: string; summary: string; status: string; disposition?: string; completed_at?: string | null }[]; recent_actions: { action_id: string; tool_id: string; status: string; detail: string; updated_at: string }[]; pending_approvals: { approval_id: string; action_id: string; tool_id: string; status: string; summary: string; expires_at: string; continuation: string }[]; health: { status: Status | string; summary: string; unavailable: string[]; degraded: string[] } };
type Capability = { id: string; label: string; state: string; detail?: string };
type IntegrationHealth = { health?: string; connected_version?: string | null; last_successful_state_sync?: string | null; last_received_event?: string | null; subscriptions_active?: boolean; discovered_counts?: Record<string, number>; mapped_count?: number; unmapped_count?: number; reconnect_attempt?: number; last_error_category?: string | null };
type Integration = { plugin_id: string; name: string; description: string; state: string; enabled: boolean; capabilities: string[]; manageable: boolean; error?: string | null; health?: IntegrationHealth };
type ZHASetupField = { name: "device_path" | "radio_type" | "baudrate" | "flow_control"; required: boolean; type: "string" | "integer"; options?: string[] };
type ZHASetup = { setup_id: string; step_id: string; fields: ZHASetupField[] };
type MutationOutcome = { status: string; operation: string; reason?: string; detail?: string; result?: unknown; evidence?: unknown };
type Connection = { configured: boolean; connected: boolean; state: string; can_connect: boolean; setup_required: boolean; household_source: string };
type SetupStatus = { state: string; available: boolean };
type Preference = { preference_id: string; content: string; category: "alerts" | "comfort" | "meals" | "shopping" | "privacy" | "other"; created_at: string; status: string; provenance?: { kind?: string } };
type User = { person_id: string; name: string; role: string; access_level: string; sentry_profile_id: string | null; sentry_onboarding_state: string; wifi_macs: string[] };

class ApiError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}
const api = async <T,>(path: string, options?: RequestInit): Promise<T> => {
  const response = await fetch(path, { ...options, credentials: "same-origin", headers: { Accept: "application/json", ...(options?.headers ?? {}) } });
  if (!response.ok) { const body = (await response.json().catch(() => ({}))) as { detail?: string }; throw new ApiError(typeof body.detail === "string" ? body.detail : "ANIMA could not complete that request", response.status); }
  return response.json() as Promise<T>;
};
const allPages = async <T,>(path: string): Promise<T[]> => {
  const items: T[] = [];
  let cursor: string | null = null;
  do {
    const separator = path.includes("?") ? "&" : "?";
    const page: { items: T[]; next_cursor: string | null } = await api<{ items: T[]; next_cursor: string | null }>(
      `${path}${separator}limit=50${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
    );
    items.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor);
  return items;
};
function StatusPill({ status }: { status: Status | string }) { return <span className={`status status-${status.toLowerCase().replaceAll("/", "-")}`}>{status.replaceAll("_", " ")}</span>; }
function Card({ title, children, className = "" }: { title: string; children: ReactNode; className?: string }) { return <section className={`card ${className}`}><div className="card-heading"><h2><Icon name={title} />{title}</h2></div>{children}</section>; }
function OutcomeNotice({ outcome }: { outcome: MutationOutcome | null }) { if (!outcome) return null; const tone = outcome.status === "SUCCEEDED" ? "success" : ["DENIED", "REQUIRE_CONFIRMATION", "REQUIRE_STRONGER_AUTH"].includes(outcome.status) ? "warning" : "error"; return <div className={`notice outcome ${tone}`} role="status" aria-live="polite"><strong>{outcome.status.replaceAll("_", " ")}</strong><span>{outcome.detail ?? outcome.reason ?? outcome.operation}</span></div>; }
function AuthenticationView({ expired = false, notice = "" }: { expired?: boolean; notice?: string }) {
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  const [setupError, setSetupError] = useState(false);
  useEffect(() => { let active = true; void api<SetupStatus>("/api/v1/setup/status").then((value) => { if (active) setSetup(value); }).catch(() => { if (active) setSetupError(true); }); return () => { active = false; }; }, []);
  return <main className="shell centered"><div className="brand-mark"><Icon name="Home" /></div><p className="eyebrow">ANIMA · HOME INTELLIGENCE</p><h1>{expired ? "Reconnect your household" : "Your home, connected"}</h1>{notice && <p className="notice error" role="alert">{notice}</p>}<p>Use your existing Home Assistant account. Credentials stay on the server.</p>{setup?.available && <a className="primary-link" href="/auth/login?connect=1"><Icon name="Integrations" /> Connect your Home Assistant</a>}<a className={setup?.available ? "" : "primary-link"} href="/auth/login">Continue with existing Home Assistant</a>{setup && <StatusPill status={setup.state} />}{setupError && <p className="muted" role="status">Setup availability could not be checked.</p>}</main>;
}
function ConnectionBanner({ connection, retry }: { connection: Connection | null; retry: () => void }) {
  const needsSetup = Boolean(connection && (connection.setup_required || !connection.configured || ["sample", "demo"].includes(connection.household_source.toLowerCase())));
  const connected = Boolean(connection?.connected && !needsSetup);
  return <section className="connection-banner" aria-label="Home Assistant connection">
    <Icon name="Integrations" /><div className="connection-copy"><strong>{connection?.connected && !needsSetup ? "Home Assistant connected" : needsSetup ? "Connect your own home" : connection ? "Home Assistant disconnected" : "Connection status unavailable"}</strong>{!connected && <small className="muted">{connection ? needsSetup ? "Connect your existing Home Assistant to use your own devices." : `Household source: ${connection.household_source.replaceAll("_", " ")}` : "Check the connection before relying on device state."}</small>}</div>
    <div className="connection-actions">{connection && <StatusPill status={connection.state} />}{connection?.can_connect && (needsSetup || !connection.connected) && <a className="primary-link" href="/auth/login?connect=1">{needsSetup ? "Connect Home Assistant" : "Reconnect Home Assistant"}</a>}{needsSetup && !connection?.can_connect && <span className="muted">Connection setup unavailable</span>}<button type="button" className={connected ? "icon-button" : undefined} onClick={retry} aria-label="Refresh connection status"><Icon name="Refresh" />{!connected && " Refresh"}</button></div>
  </section>;
}
const sectionActions: Record<string, [string, string][]> = {
  Home: [["Review my home", "Review my household's current status and highlight anything that needs attention."], ["Plan my day", "Help me plan today using my household tasks and calendar."]],
  Devices: [["Check my devices", "Review my commissioned devices and explain any stale or unavailable states."], ["Help add a device", "Guide me through pairing and assigning a new device to a room."]],
  Spaces: [["Organize rooms", "Help me organize my household rooms and zones."]],
  Scenes: [["Plan a scene", "Help me plan a scene using my available power controls. Ask me which devices and states I want."]],
  Automations: [["Plan a routine", "Help me plan a supported event-to-power automation. Ask me about the trigger and intended action."]],
  Alerts: [["Review alert rules", "Review my alert policies and help me decide what should need attention."]],
  Notifications: [["Review delivery", "Review my notification route and recent delivery results. Do not assume human receipt."]],
  Anima: [["Home status", "What needs attention in my home right now?"], ["Today's agenda", "What is on my household calendar today?"], ["Help me plan", "Help me plan a household task. Ask me what I want to accomplish."]],
  "Tasks & Calendar": [["Plan a reminder", "Help me prepare a reminder. Ask me what to remember and when."], ["Review my agenda", "Review my current tasks and calendar."]],
  Activity: [["Explain activity", "Explain recent household activity and any uncertain action outcomes."]],
  Capabilities: [["What can you do?", "Explain which household capabilities are currently available and which are unavailable."]],
  Integrations: [["Check connections", "Review integration health and explain safe recovery options."]],
  Backups: [["Review recovery", "Explain my backup status and what restoring would change. Do not restore anything."]],
  Preferences: [["Remember a preference", "Help me write a household preference. Ask me what I would like you to remember."]],
  Settings: [["Personalize my view", "Help me choose interface settings for this screen."]],
};
function QuickActions({ section, prepare }: { section: string; prepare: (intent: string) => void }) {
  return <div className="quick-actions" aria-label={`Assistant quick actions for ${section}`}>{(sectionActions[section] ?? []).map(([label, intent]) => <button type="button" className="quick-action" key={label} onClick={() => prepare(intent)}><span className="quick-action-icon"><Icon name="Anima" /></span>{label}<Icon name="ArrowRight" /></button>)}</div>;
}
function SummaryCards({ items }: { items: [string, number, string][] }) {
  return <div className="summary-grid">{items.map(([label, value, icon]) => <div className="summary-card" key={label}><Icon name={icon} /><strong className="summary-value">{value}</strong><span className="summary-label">{label}</span></div>)}</div>;
}
function PowerControls({ id, label, state, mutate }: { id: string; label: string; state: string; mutate: (path: string, payload?: Record<string, unknown>) => Promise<MutationOutcome | null> }) {
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const setPower = async (desired_on: boolean) => { if (lock.current) return; lock.current = true; setBusy(true); try { await mutate(`/api/v1/controls/${id}`, { desired_on }); } finally { lock.current = false; setBusy(false); } };
  return <span className="button-row" role="group" aria-label={`Power for ${label}`} aria-busy={busy}><button disabled={busy} aria-label={`Turn ${label} on`} aria-pressed={state.toLowerCase() === "on"} onClick={() => void setPower(true)}><Icon name="Power" /> On</button><button disabled={busy} aria-label={`Turn ${label} off`} aria-pressed={state.toLowerCase() === "off"} onClick={() => void setPower(false)}>Off</button></span>;
}
function useMutation(csrf: string, refresh: () => Promise<void>, setError: (value: string) => void, setOutcome: (value: MutationOutcome) => void, onAuthFailure: () => void) {
  return async (path: string, payload: Record<string, unknown> = {}): Promise<MutationOutcome | null> => { try { setError(""); const result = await api<MutationOutcome>(path, { method: "POST", body: JSON.stringify({ payload }), headers: { "Content-Type": "application/json", "X-Anima-CSRF": csrf, Origin: window.location.origin } }); setOutcome(result); window.setTimeout(() => { void refresh(); }, 0); return result; } catch (err) { if (err instanceof ApiError && err.status === 401) onAuthFailure(); else setError(err instanceof Error ? err.message : "ANIMA could not complete that request"); return null; } };
}

function App() {
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null); const [home, setHome] = useState<Home | null>(null); const [settings, setSettings] = useState<Settings | null>(null); const [voiceSettings, setVoiceSettings] = useState<SentryVoiceSettings | null>(null); const [capabilities, setCapabilities] = useState<Capability[]>([]); const [integrations, setIntegrations] = useState<Integration[]>([]); const [devices, setDevices] = useState<ProviderDevice[]>([]); const [spaces, setSpaces] = useState<Space[]>([]); const [alertPolicies, setAlertPolicies] = useState<AlertPolicy[]>([]); const [alertEvents, setAlertEvents] = useState<AlertEvent[]>([]); const [alertNextCursor, setAlertNextCursor] = useState<string | null>(null); const [alertLoading, setAlertLoading] = useState(false); const [notificationRoutes, setNotificationRoutes] = useState<NotificationRoute[]>([]); const [backups, setBackups] = useState<BackupRecord[]>([]); const [scenes, setScenes] = useState<Scene[]>([]); const [automations, setAutomations] = useState<Automation[]>([]); const [preferences, setPreferences] = useState<Preference[]>([]); const [users, setUsers] = useState<User[]>([]); const [tab, setTab] = useState("Home"); const reply = ""; const [error, setError] = useState(""); const [outcome, setOutcome] = useState<MutationOutcome | null>(null);
  const refreshGeneration = useRef(0);
  const authGeneration = useRef(0);
  const refreshInFlight = useRef<Promise<void> | null>(null);
  const refreshPending = useRef(false);
  const snapshotAbort = useRef<AbortController | null>(null);
  const initialSnapshotStarted = useRef(false);
  const pauseStream = useRef<(() => void) | null>(null);
  const resumeStream = useRef<(() => void) | null>(null);
  const [connection, setConnection] = useState<Connection | null>(null);
  const [voiceSuggestion, setVoiceSuggestion] = useState("");
  const voicePanelRef = useRef<HTMLHeadingElement>(null);
  const prepare = (intent: string) => { setVoiceSuggestion(intent); setTab("Anima"); window.requestAnimationFrame(() => voicePanelRef.current?.focus()); };
  const clearProtectedState = () => {
      authGeneration.current += 1;
      setBootstrap(null); setHome(null); setSettings(null); setVoiceSettings(null); setConnection(null);
      setCapabilities([]); setIntegrations([]); setDevices([]); setSpaces([]);
      setAlertPolicies([]); setAlertEvents([]); setAlertNextCursor(null); setAlertLoading(false);
      setNotificationRoutes([]); setBackups([]); setScenes([]); setAutomations([]); setPreferences([]); setUsers([]);
      setVoiceSuggestion(""); setOutcome(null);
  };
  const expireSession = () => {
    refreshGeneration.current += 1; snapshotAbort.current?.abort(); pauseStream.current?.();
    clearProtectedState(); setError("AUTHENTICATION_REQUIRED");
  };
  const loadSnapshot = async () => {
    const generation = ++refreshGeneration.current;
    const controller = new AbortController(); snapshotAbort.current = controller;
    let timedOut = false;
    let authFailure = "";
    const timeout = window.setTimeout(() => { timedOut = true; controller.abort(); }, 10000);
    const read = <T,>(path: string): Promise<T> => api<T>(path, { signal: controller.signal }).catch((err) => {
      if (err instanceof ApiError && (err.status === 401 || ["AUTHENTICATION_REQUIRED", "SESSION_EXPIRED"].includes(err.message))) {
        if (generation === refreshGeneration.current && !authFailure) {
          authFailure = err.message === "SESSION_EXPIRED" ? "SESSION_EXPIRED" : "AUTHENTICATION_REQUIRED";
          clearProtectedState(); setError(authFailure); controller.abort();
        }
      }
      throw err;
    });
    // Stage values until authentication has resolved; a failed section must not discard other reads.
    const section = <T,>(label: string, path: string, apply: (value: T) => void) => ({
      label, path, result: read<T>(path).then((value) => () => apply(value)),
    });
    setError("");
    const sections = [
      section<Bootstrap>("Session", "/api/v1/bootstrap", setBootstrap),
      section<Home>("Home", "/api/v1/home", setHome),
      section<{ items: Capability[] }>("Capabilities", "/api/v1/capabilities", (value) => setCapabilities(value.items)),
      section<{ items: Integration[] }>("Integrations", "/api/v1/integrations", (value) => setIntegrations(value.items)),
      section<{ settings: Settings }>("Settings", "/api/v1/settings", (value) => setSettings(value.settings)),
      section<{ settings: SentryVoiceSettings }>("SENTRY voice settings", "/api/v1/sentry/voice-settings", (value) => setVoiceSettings(value.settings)),
      section<{ items: ProviderDevice[] }>("Devices", "/api/v1/devices", (value) => setDevices(value.items)),
      section<{ items: Space[] }>("Spaces", "/api/v1/places", (value) => setSpaces(value.items)),
      section<{ items: AlertPolicy[] }>("Alert policies", "/api/v1/alerts/policies", (value) => setAlertPolicies(value.items)),
      section<Page<AlertEvent>>("Alert events", "/api/v1/alerts/events", (value) => { setAlertEvents(value.items); setAlertNextCursor(value.next_cursor); }),
      section<{ items: NotificationRoute[] }>("Notification routes", "/api/v1/notifications/routes", (value) => setNotificationRoutes(value.items)),
      section<{ items: BackupRecord[] }>("Backups", "/api/v1/backups", (value) => setBackups(value.items)),
      section<{ items: Scene[] }>("Scenes", "/api/v1/scenes", (value) => setScenes(value.items)),
      section<{ items: Automation[] }>("Automations", "/api/v1/automations", (value) => setAutomations(value.items)),
      section<{ items: Preference[] }>("Preferences", "/api/v1/preferences", (value) => setPreferences(value.items)),
      section<{ items: User[] }>("Users", "/api/v1/users", (value) => setUsers(value.items)),
      section<Connection>("Connection", "/api/v1/connection", setConnection),
    ];
    try {
      const results = await Promise.allSettled(sections.map((item) => item.result));
      if (generation !== refreshGeneration.current || authFailure || (controller.signal.aborted && !timedOut)) return;
      const failures: string[] = [];
      results.forEach((result, index) => {
        if (result.status === "fulfilled") {
          // A failed bootstrap cannot establish which household the other data belongs to.
          if (results[0].status === "fulfilled") result.value();
        } else {
          const item = sections[index];
          const timeout = timedOut && result.reason instanceof DOMException && result.reason.name === "AbortError";
          failures.push(`${item.label} (${item.path})${timeout ? " timed out" : " unavailable"}`);
          if (item.path === "/api/v1/connection") setConnection(null);
        }
      });
      if (failures.length) setError(`Refresh incomplete: ${failures.join("; ")}. Unrefreshed sections may show older data; try Refresh again.`);
    } finally {
      controller.abort(); window.clearTimeout(timeout);
      if (snapshotAbort.current === controller) snapshotAbort.current = null;
    }
  };
  const refresh = (): Promise<void> => {
    refreshPending.current = true;
    if (document.hidden || (!document.hasFocus() && initialSnapshotStarted.current)) return Promise.resolve();
    if (refreshInFlight.current) return refreshInFlight.current;
    initialSnapshotStarted.current = true;
    // Release this tab's HTTP/1 stream slot before competing snapshot reads.
    pauseStream.current?.();
    const run = async () => {
      do { refreshPending.current = false; await loadSnapshot(); } while (refreshPending.current && !document.hidden && document.hasFocus());
    };
    const pending = run().finally(() => { refreshInFlight.current = null; resumeStream.current?.(); });
    refreshInFlight.current = pending;
    return pending;
  };
  const loadOlderAlerts = async () => { if (!alertNextCursor || alertLoading) return; const generation = authGeneration.current; setAlertLoading(true); try { setError(""); const page = await api<Page<AlertEvent>>(`/api/v1/alerts/events?limit=50&cursor=${encodeURIComponent(alertNextCursor)}`); if (generation !== authGeneration.current) return; setAlertEvents((current) => [...current, ...page.items]); setAlertNextCursor(page.next_cursor); } catch (err) { if (generation !== authGeneration.current) return; setError(err instanceof Error ? err.message : "ANIMA could not load older alerts"); } finally { if (generation === authGeneration.current) setAlertLoading(false); } };
  useEffect(() => { void refresh(); }, []);
  useEffect(() => {
    let events: EventSource | null = null;
    let invalidationTimer: number | undefined;
    let fallbackTimer: number | undefined;
    const close = () => { events?.close(); events = null; window.clearTimeout(invalidationTimer); window.clearTimeout(fallbackTimer); };
    const invalidate = () => {
      window.clearTimeout(invalidationTimer);
      invalidationTimer = window.setTimeout(() => { void refresh(); }, 75);
    };
    const synchronize = (refetch: boolean) => {
      if (document.hidden) { close(); snapshotAbort.current?.abort(); refreshPending.current = true; return; }
      if (!document.hasFocus()) { close(); refreshPending.current = true; return; }
      if (bootstrap && !events && !refreshInFlight.current) {
        events = new EventSource("/api/v1/events");
        events.onerror = () => {
          // EventSource hides HTTP status (including the per-session stream cap).
          // Stop its automatic reconnect; retry reads at a bounded foreground cadence.
          events?.close(); events = null;
          window.clearTimeout(fallbackTimer);
          if (!document.hidden && document.hasFocus()) fallbackTimer = window.setTimeout(() => { void refresh(); }, 15000);
        };
        ["home.invalidated", "tasks.changed", "calendar.changed", "alerts.changed", "activity.changed", "conversation.completed", "capabilities.changed", "preferences.changed", "refresh.required"].forEach((name) => events!.addEventListener(name, invalidate));
      }
      if (refetch) void refresh();
    };
    const visibility = () => synchronize(true);
    const blur = () => { close(); refreshPending.current = true; };
    const suspend = () => { close(); snapshotAbort.current?.abort(); };
    pauseStream.current = close;
    resumeStream.current = () => synchronize(false);
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("blur", blur);
    window.addEventListener("focus", visibility);
    window.addEventListener("pagehide", suspend);
    window.addEventListener("pageshow", visibility);
    synchronize(false);
    return () => { close(); pauseStream.current = null; resumeStream.current = null; document.removeEventListener("visibilitychange", visibility); window.removeEventListener("blur", blur); window.removeEventListener("focus", visibility); window.removeEventListener("pagehide", suspend); window.removeEventListener("pageshow", visibility); };
  }, [Boolean(bootstrap)]);
  useEffect(() => { if (!settings) return; const root = document.documentElement; root.dataset.appearance = settings.appearance; root.dataset.accent = settings.accent; root.dataset.density = settings.density; root.dataset.textScale = settings.text_scale; root.dataset.reducedMotion = settings.reduced_motion ? "true" : "false"; root.dataset.displayMode = settings.display_mode; }, [settings]);
  const mutate = useMutation(bootstrap?.csrf_token ?? "", refresh, setError, setOutcome, expireSession); const greeting = useMemo(() => bootstrap ? `Welcome, ${bootstrap.identity.display_name}.` : "Connecting to Anima…", [bootstrap]);
  if (!bootstrap || !home || !settings) { if (error === "AUTHENTICATION_REQUIRED") return <AuthenticationView />; if (error === "SESSION_EXPIRED") return <AuthenticationView expired />; return <main className="shell centered"><div className="brand-mark">A</div><h1>Anima</h1><p>{error || "Connecting to your home…"}</p>{error && <button onClick={() => void refresh()}>Try again</button>}</main>; }
  const degraded = capabilities.some((item) => ["degraded", "unavailable"].includes(item.state.toLowerCase()));
  const navGroups = [
    ["Household", ["Home", "Devices", "Spaces", "Scenes", "Automations", "Routines"]],
    ["Assistant", ["Alerts", "Notifications", "Anima", "Tasks & Calendar", "Activity"]],
    ["Manage", ["Users", "Capabilities", "Integrations", "Backups", "Preferences", "Settings"]],
  ] as const;
  const presentDevices = devices.filter((item) => item.external_object_kind === "device" && item.present);
  const enabled = <T extends { enabled: boolean },>(items: T[]) => items.filter((item) => item.enabled).length;
  const summaries: Record<string, [string, number, string][]> = {
    Home: [["Devices", presentDevices.length, "Devices"], ["Rooms & zones", spaces.filter((item) => ["ROOM", "ZONE"].includes(item.kind)).length, "Spaces"], ["Enabled scenes", enabled(scenes), "Scenes"], ["Pending approvals", home.pending_approvals.length, "Alerts"]],
    Devices: [["Discovered", presentDevices.length, "Devices"], ["Commissioned", presentDevices.filter((item) => item.metadata.mapping_status === "MAPPED").length, "Home"], ["Needs a room", presentDevices.filter((item) => item.metadata.mapping_status !== "MAPPED").length, "Spaces"]],
    Spaces: [["Rooms", spaces.filter((item) => item.kind === "ROOM").length, "Spaces"], ["Zones", spaces.filter((item) => item.kind === "ZONE").length, "Spaces"]],
    Scenes: [["Saved scenes", scenes.length, "Scenes"], ["Enabled", enabled(scenes), "Power"], ["Available controls", home.controls.length, "Devices"]],
    Automations: [["Rules", automations.length, "Automations"], ["Enabled", enabled(automations), "Power"]],
    Alerts: [["Policies", alertPolicies.length, "Alerts"], ["Enabled", enabled(alertPolicies), "Power"], ["Loaded events", alertEvents.length, "Activity"]],
    Notifications: [["Routes", notificationRoutes.length, "Notifications"], ["Enabled", enabled(notificationRoutes), "Power"], ["Recent notifications", home.notifications.length, "Activity"]],
    Activity: [["Recent activity", home.activity.length, "Activity"], ["Recent actions", home.recent_actions.length, "Power"], ["Pending approvals", home.pending_approvals.length, "Alerts"]],
    Capabilities: [["Registered", capabilities.length, "Capabilities"], ["Degraded / unavailable", capabilities.filter((item) => ["degraded", "unavailable"].includes(item.state.toLowerCase())).length, "Alerts"]],
    Integrations: [["Registered", integrations.length, "Integrations"], ["Enabled", enabled(integrations), "Power"]],
    Backups: [["Snapshots", backups.length, "Backups"], ["Valid snapshots", backups.filter((item) => item.restorable).length, "Check"]],
    Preferences: [["Saved preferences", preferences.length, "Preferences"]],
    Users: [["Household users", users.length, "Users"], ["Face profiles", users.filter((item) => item.sentry_onboarding_state === "ACTIVE").length, "Person"], ["Wi‑Fi hints", users.filter((item) => item.wifi_macs.length > 0).length, "Integrations"]],
  };
  const descriptions: Record<string, string> = {
    Routines: "Your household's owner-declared schedules and expectations.",
    Home: "Your household at a glance.", Devices: "Pair, place, and control your devices.", Spaces: "A place for every device.",
    Scenes: "Set the mood with saved device states.", Automations: "When something changes, put your routine to work.", Alerts: "Choose what deserves attention.",
    Notifications: "Choose when and where household alerts are routed.", Anima: "Voice control through your existing SENTRY desktop.", "Tasks & Calendar": "Make room for what matters.",
    Activity: "Recent observations and recorded outcomes.", Capabilities: "See what your household can use.", Integrations: "Manage your connected services.",
    Backups: "Protect and recover your household records.", Preferences: "Help Anima understand your household choices.", Settings: "Make this screen feel at home.", Users: "Manage household identity, SENTRY access, and Wi‑Fi presence hints.",
  };
  return <div className="app-shell">
    <aside className="sidebar"><a className="skip-link" href="#main-content">Skip to content</a><div className="brand"><div className="brand-mark"><Icon name="Home" /></div><div><strong>Anima</strong><small>home intelligence</small></div></div>
      <nav aria-label="Primary navigation">{navGroups.map(([group, items]) => <div className="nav-group" key={group}><p className="nav-group-label">{group}</p>{items.map((item) => <button key={item} aria-label={item} aria-current={tab === item ? "page" : undefined} className={tab === item ? "nav-item active" : "nav-item"} onClick={() => setTab(item)}><span className="nav-icon"><Icon name={item} /></span><span className="nav-label">{item}</span>{item === "Alerts" && home.pending_approvals.length > 0 && <span className="nav-count" aria-hidden="true">{home.pending_approvals.length}</span>}</button>)}</div>)}</nav>
      <div className="sidebar-footer"><StatusPill status={degraded ? "degraded" : "available"} /><span>{degraded ? "Some capabilities need attention" : "Core available"}</span></div>
    </aside>
    <main className="content" id="main-content" tabIndex={-1}>
      <header className="topbar"><div><p className="eyebrow">{bootstrap.household.name}</p><h1>{tab === "Home" ? greeting : tab}</h1></div><div className="topbar-actions"><button className="avatar" aria-label="Current household member" title={bootstrap.identity.display_name} onClick={() => setTab("Settings")}>{bootstrap.identity.display_name.slice(0, 1).toUpperCase()}</button></div></header>
      <OutcomeNotice outcome={outcome} />{error && <div className="notice error" role="alert">{error}</div>}
      <ConnectionBanner connection={connection} retry={() => void refresh()} />
      <section className="section-intro" aria-label={`${tab} overview`}><div className="section-heading"><p className="section-description">{descriptions[tab]}</p><span className="assistant-note">Assistant shortcuts show suggestions to ask SENTRY by voice; nothing is sent.</span></div><QuickActions section={tab} prepare={prepare} />{summaries[tab] && <SummaryCards items={summaries[tab]} />}</section>
      {tab === "Home" && <HomeView home={home} settings={settings} mutate={mutate} reply={reply} />}
      {tab === "Devices" && <DevicesView devices={devices} rooms={home.rooms} mutate={mutate} />}
      {tab === "Spaces" && <SpacesView spaces={spaces} mutate={mutate} />}
      {tab === "Routines" && <><FamilyRoutines mutate={mutate} onAuthFailure={expireSession} /><HouseholdPresencePanel mutate={mutate} onAuthFailure={expireSession} /></>}
      {tab === "Scenes" && <ScenesView scenes={scenes} controls={home.controls} mutate={mutate} />}
      {tab === "Automations" && <AutomationsView automations={automations} devices={devices} controls={home.controls} mutate={mutate} />}
      {tab === "Alerts" && <AlertPoliciesView policies={alertPolicies} devices={devices} rooms={home.rooms} mutate={mutate} events={alertEvents} nextCursor={alertNextCursor} loading={alertLoading} loadOlder={loadOlderAlerts} />}
      {tab === "Notifications" && <NotificationRoutesView routes={notificationRoutes} mutate={mutate} />}
      {tab === "Anima" && <section className="card conversation" aria-labelledby="sentry-voice-heading"><h2 id="sentry-voice-heading" ref={voicePanelRef} tabIndex={-1}><Icon name="Anima" /> SENTRY voice control</h2><p>Speak to your existing SENTRY desktop using its wake and microphone controls. SENTRY handles voice replies and speech playback.</p><p className="muted">This dashboard does not start a microphone, send conversational text, or confirm that the desktop is listening.</p><p role="status">Reported household voice status: <StatusPill status={home.voice.status} /> · {home.voice.label}</p>{voiceSuggestion && <aside className="assistant-note"><strong>You can ask SENTRY by voice</strong><p>{voiceSuggestion}</p><small>Suggestion only — nothing has been sent.</small></aside>}<button type="button" onClick={() => setTab("Activity")}>View household activity</button></section>}
      {tab === "Tasks & Calendar" && <TaskCalendar mutate={mutate} />}
      {tab === "Activity" && <Card title="Recent activity"><ul className="clean-list activity-timeline">{home.activity.length ? home.activity.map((item, index) => <li key={`${item.summary}-${index}`}><Icon name="Activity" /><span>{item.summary}</span><StatusPill status={item.status} /></li>) : <li className="empty-state">No household activity recorded.</li>}</ul></Card>}
      {tab === "Capabilities" && <Capabilities items={capabilities} />}
      {tab === "Integrations" && <><RingConnectionPanel csrfToken={bootstrap.csrf_token} onAuthFailure={expireSession} /><VendorConnectionsPanel onAuthFailure={expireSession} /><ManagedIntegrationsView items={integrations} mutate={mutate} /></>}
      {tab === "Backups" && <BackupsView backups={backups} mutate={mutate} />}
      {tab === "Preferences" && <><PreferencesPanel mutate={mutate} onAuthFailure={expireSession} /><InitiativePanel mutate={mutate} onAuthFailure={expireSession} /><KnowledgePanel mutate={mutate} onAuthFailure={expireSession} /></>}
      {tab === "Users" && <UsersPanel mutate={mutate} onAuthFailure={expireSession} />}
      {tab === "Settings" && <SettingsPanel value={settings} voice={voiceSettings} csrf={bootstrap.csrf_token} onSaved={setSettings} onVoiceSaved={setVoiceSettings} setError={setError} setOutcome={setOutcome} />}
    </main>
  </div>;
}

function HomeView({ home, settings, mutate, reply }: { home: Home; settings: Settings; mutate: (path: string, payload?: Record<string, unknown>) => Promise<MutationOutcome | null>; reply: string }) {
  const observedDevices = home.rooms.flatMap((room) => room.devices);
  const onCount = observedDevices.filter((device) => device.state.toLowerCase() === "on").length;
  const offCount = observedDevices.filter((device) => device.state.toLowerCase() === "off").length;
  const widgets: Record<string, ReactNode> = {
    status: <Card title="At a glance" className="hero"><div className="overview-visual"><StatusRing value={onCount + offCount} total={observedDevices.length} label="Devices with on/off state" /><div className="overview-meters"><Meter value={onCount} max={observedDevices.length} label="On" /><Meter value={offCount} max={observedDevices.length} label="Off" /><Meter value={observedDevices.length - onCount - offCount} max={observedDevices.length} label="Other / unknown state" /></div></div><p className="muted">Current room snapshot · {observedDevices.length} devices. No historical telemetry.</p><div className="metric-row"><div><span>Security</span><StatusPill status={home.security.status} /></div><div><span>Weather</span><StatusPill status={home.weather.status} /></div><div><span>Health</span><StatusPill status={home.health.status} /></div></div><details className="integration-details"><summary>Household details</summary><p>{home.household.summary}</p><p>{home.health.summary}</p></details></Card>,
    presence: <Card title="People at home"><ul className="clean-list">{home.presence.people.map((person) => <li key={person.name}><span><span className="person-dot" />{person.name}</span><StatusPill status={person.state} /></li>)}</ul></Card>,
    weather: <Card title="Weather"><p className="muted">{home.weather.summary}</p></Card>,
    agenda: <Card title="Coming up"><ul className="clean-list">{home.calendar.map((event) => <li key={event.event_id}><span>{event.title}</span><time>{new Date(event.start_at).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" })}</time></li>)}</ul></Card>,
    tasks: <Card title="Things to do"><ul className="clean-list">{home.tasks.map((task) => <li key={task.task_id}><span>{task.title}</span><StatusPill status={task.status} /></li>)}</ul></Card>,
    controls: <Card title="Home controls"><ul className="clean-list">{home.controls.length ? home.controls.map((control) => <li key={control.control_id}><span>{control.label}<small className="muted control-state">{control.state}</small></span><PowerControls id={control.control_id} label={control.label} state={control.state} mutate={mutate} /></li>) : <li className="muted">No commissioned controls are available.</li>}</ul></Card>,
    conversation: <Card title="Anima"><p className="muted">{reply || "Use SENTRY on your desktop for voice control."}</p></Card>,
    activity: <Card title="Activity"><ul className="clean-list">{home.activity.length ? home.activity.map((item, index) => <li key={`${item.summary}-${index}`}><span>{item.summary}</span><StatusPill status={item.status} /></li>) : <li className="muted">No household activity recorded.</li>}</ul></Card>,
    household: <Card title="Rooms & devices"><div className="room-list">{home.rooms.length ? home.rooms.map((room) => <div className="room" key={room.place_id}><strong>{room.name}</strong><small className="muted">{room.kind}</small>{room.devices.length ? <ul className="clean-list nested-list">{room.devices.map((device) => <li key={device.device_id}><span>{device.name}<small className="muted">{device.kind}</small></span><StatusPill status={device.state} /></li>)}</ul> : <p className="muted">No commissioned devices in this place.</p>}</div>) : <p className="muted">No commissioned rooms or devices are available.</p>}</div></Card>,
    reports: <Card title="Notifications & recent actions"><h3>Notifications</h3><ul className="clean-list">{home.notifications.length ? home.notifications.map((item) => <li key={item.notification_id}><span>{item.summary}<small className="muted">{item.importance ?? "household"}</small></span><StatusPill status={item.status} /></li>) : <li className="muted">No notifications recorded.</li>}</ul><h3 className="subheading">Reports</h3><ul className="clean-list">{home.reports.length ? home.reports.map((item) => <li key={item.report_id}><span>{item.summary}<small className="muted">{item.disposition ?? "No disposition"}</small></span><StatusPill status={item.status} /></li>) : <li className="muted">No episode reports recorded.</li>}</ul><h3 className="subheading">Recent actions</h3><ul className="clean-list">{home.recent_actions.length ? home.recent_actions.map((item) => <li key={item.action_id}><span>{item.tool_id}<small className="muted">{item.detail}</small></span><StatusPill status={item.status} /></li>) : <li className="muted">No governed actions recorded.</li>}</ul>{home.pending_approvals.length > 0 && <div className="pending-approval"><strong>Pending confirmation</strong>{home.pending_approvals.map((approval) => <div className="notice warning" key={approval.approval_id}><span>{approval.summary}<small className="muted">Expires {new Date(approval.expires_at).toLocaleTimeString()}</small></span><span className="button-row"><button onClick={() => void mutate(`/api/v1/approvals/${approval.approval_id}`, { decision: "APPROVE" })}>Approve</button><button onClick={() => void mutate(`/api/v1/approvals/${approval.approval_id}`, { decision: "REJECT" })}>Reject</button></span></div>)}</div>}</Card>,
    health: <Card title="System health"><p className="muted">{home.health.summary}</p><StatusPill status={home.health.status} />{home.health.unavailable.length > 0 && <p className="muted"><strong>Unavailable:</strong> {home.health.unavailable.join(", ")}</p>}{home.health.degraded.length > 0 && <p className="muted"><strong>Degraded:</strong> {home.health.degraded.join(", ")}</p>}</Card>,
  };
  const order = settings.widget_order.filter((id) => settings.visible_widgets.includes(id));
  return <div className="dashboard">{order.map((id) => <div className="widget" data-widget={id} key={id}>{widgets[id]}</div>)}</div>;
}
function SpacesView({ spaces, mutate }: { spaces: Space[]; mutate: (path: string, payload?: Record<string, unknown>) => Promise<MutationOutcome | null> }) {
  const root = spaces.find((space) => space.kind === "HOUSEHOLD");
  const parents = spaces.filter((space) => ["HOUSEHOLD", "PROPERTY", "BUILDING", "FLOOR", "ROOM", "ZONE", "OUTSIDE"].includes(space.kind));
  const [name, setName] = useState(""); const [kind, setKind] = useState<"ROOM" | "ZONE">("ROOM"); const [parentId, setParentId] = useState(root?.place_id ?? ""); const [editing, setEditing] = useState<string | null>(null); const [editName, setEditName] = useState(""); const [editParentId, setEditParentId] = useState("");
  useEffect(() => { if (!parentId && root) setParentId(root.place_id); }, [parentId, root?.place_id]);
  const create = async (event: React.FormEvent) => { event.preventDefault(); const result = await mutate("/api/v1/places/create", { name, kind, parent_id: parentId }); if (result?.status === "SUCCEEDED") { setName(""); } };
  const saveName = async (event: React.FormEvent, space: Space) => { event.preventDefault(); const result = await mutate("/api/v1/places/rename", { place_id: space.place_id, name: editName }); if (result?.status === "SUCCEEDED") setEditing(null); };
  const move = async (event: React.FormEvent, space: Space) => { event.preventDefault(); if (!editParentId || editParentId === space.parent_id) { setEditing(null); return; } const result = await mutate("/api/v1/places/move", { place_id: space.place_id, parent_id: editParentId }); if (result?.status === "SUCCEEDED") setEditing(null); };
  const beginEdit = (space: Space) => { setEditing(space.place_id); setEditName(space.name); setEditParentId(space.parent_id ?? root?.place_id ?? ""); };
  const descendantsOf = (placeId: string) => { const descendants = new Set<string>(); let changed = true; while (changed) { changed = false; spaces.forEach((candidate) => { if (candidate.parent_id && (candidate.parent_id === placeId || descendants.has(candidate.parent_id)) && !descendants.has(candidate.place_id)) { descendants.add(candidate.place_id); changed = true; } }); } return descendants; };
  return <div className="dashboard"><Card title="Create a room or zone"><p className="muted">Create a place, then assign your devices.</p><form className="stack" onSubmit={(event) => void create(event)}><label>Name<input required maxLength={120} value={name} onChange={(event) => setName(event.target.value)} /></label><label>Type<select value={kind} onChange={(event) => setKind(event.target.value as "ROOM" | "ZONE")}><option value="ROOM">Room</option><option value="ZONE">Zone</option></select></label><label>Contained in<select required value={parentId} onChange={(event) => setParentId(event.target.value)}>{parents.map((parent) => <option key={parent.place_id} value={parent.place_id}>{parent.name} · {parent.kind.toLowerCase()}</option>)}</select></label><button type="submit" disabled={!parentId}>Create place</button></form></Card><Card title="Household places"><p className="muted">Move places within this household. Only empty places can be removed.</p>{spaces.length ? <ul className="clean-list list-spaced">{spaces.map((space) => <li className="space-row" key={space.place_id}>{editing === space.place_id ? <div className="stack"><form className="stack" onSubmit={(event) => void saveName(event, space)}><label>Name<input required maxLength={120} aria-label={`Name for ${space.name}`} value={editName} onChange={(event) => setEditName(event.target.value)} /><button type="submit">Save name</button></label></form><form className="stack" onSubmit={(event) => void move(event, space)}><label>Contained in<select required aria-label={`Parent for ${space.name}`} value={editParentId} onChange={(event) => setEditParentId(event.target.value)}>{parents.filter((parent) => parent.place_id !== space.place_id && !descendantsOf(space.place_id).has(parent.place_id)).map((parent) => <option key={parent.place_id} value={parent.place_id}>{parent.name} · {parent.kind.toLowerCase()}</option>)}</select><button type="submit">Move place</button></label></form><button type="button" onClick={() => setEditing(null)}>Done</button></div> : <><span><strong>{space.name}</strong><small className="muted">{space.kind}{space.parent_id ? ` · in ${spaces.find((parent) => parent.place_id === space.parent_id)?.name ?? "household"}` : ""}</small></span>{["ROOM", "ZONE"].includes(space.kind) && <span className="button-row"><button onClick={() => beginEdit(space)}>Manage</button><button onClick={() => { if (window.confirm(`Remove ${space.name}? It must be empty.`)) void mutate("/api/v1/places/remove", { place_id: space.place_id }); }}>Remove</button></span>}</>}</li>)}</ul> : <p className="muted">No commissioned household places are available.</p>}</Card></div>;
}
function deviceDisplayName(item: ProviderDevice, rooms: Room[] = []) {
  if (item.metadata.mapping_status === "MAPPED" && item.metadata.canonical_target_id) {
    if (item.canonical_name?.trim()) return item.canonical_name;
    const matches = rooms.flatMap(room => room.devices.filter(device => device.device_id === item.metadata.canonical_target_id));
    if (matches.length === 1 && matches[0].name?.trim()) return matches[0].name;
  }
  return String(item.metadata.name_by_user ?? item.metadata.name ?? "Unnamed device");
}
function LastReported({ reading }: { reading: LastReportedState & { truth_status?: string } }) {
  if (reading.truth_status !== "STALE" || !["OPEN", "CLOSED"].includes(reading.last_reported_state ?? "") || reading.last_reported_source !== "ANIMA_TRUTH" || !reading.last_reported_at || Number.isNaN(Date.parse(reading.last_reported_at))) return null;
  return <small className="muted">Last reported: {reading.last_reported_state} · <time dateTime={reading.last_reported_at}>{new Date(reading.last_reported_at).toLocaleString()}</time> · ANIMA Truth · not current</small>;
}
function CapabilityDetails({ capabilities, label }: { capabilities: DeviceCapability[]; label: string }) {
  const chips = <span className="state-grid">{capabilities.map((capability, index) => <span className="capability-chip" key={`${capability.type}-${index}`}>{capability.label || capability.type}<small>State: {capability.state} · Truth: {capability.truth_status}</small><LastReported reading={capability} /></span>)}</span>;
  return capabilities.length > 2 ? <details className="integration-details" aria-label={`Capabilities for ${label}`}><summary>Capabilities ({capabilities.length})</summary>{chips}</details> : chips;
}
function DevicesView({ devices, rooms, mutate }: { devices: ProviderDevice[]; rooms: Room[]; mutate: (path: string, payload?: Record<string, unknown>) => Promise<MutationOutcome | null> }) {
  const [duration, setDuration] = useState("60");
  const [commissioningId, setCommissioningId] = useState<string | null>(null);
  const [editing, setEditing] = useState<ProviderDevice | null>(null);
  const [name, setName] = useState("");
  const [placeId, setPlaceId] = useState(rooms[0]?.place_id ?? "");
  const discovered = devices.filter((item) => item.external_object_kind === "device" && item.present);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [roomFilter, setRoomFilter] = useState("all");
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const syncPending = useRef(false);
  const canonicalPlacement = (item: ProviderDevice) => {
    if (!item.present || item.metadata.mapping_status !== "MAPPED" || !item.metadata.canonical_target_id) return null;
    const matches = rooms.flatMap((room) => room.devices.filter((device) => device.device_id === item.metadata.canonical_target_id).map((device) => ({ room, device })));
    if (matches.length !== 1) return null;
    const match = matches[0];
    return ["ROOM", "ZONE"].includes(match.room.kind) && match.room.place_id?.trim() && match.device.name?.trim() ? match : null;
  };
  const syncCapabilities = async (item: ProviderDevice) => {
    const placement = canonicalPlacement(item);
    if (!placement || syncPending.current) return;
    syncPending.current = true;
    setSyncingId(item.device_handle);
    try {
      await mutate("/api/v1/devices/commission", { device_handle: item.device_handle, name: placement.device.name, place_id: placement.room.place_id });
    } finally {
      syncPending.current = false;
      setSyncingId(null);
    }
  };
  const deviceRoom = (item: ProviderDevice) => rooms.find((room) => room.devices.some((device) => device.device_id === item.metadata.canonical_target_id));
  const filtered = discovered.filter((item) => {
    const mapped = item.metadata.mapping_status === "MAPPED";
    const matchesFilter = filter === "all" || (filter === "commissioned" && mapped) || (filter === "new" && !mapped) || (filter === "attention" && mapped && item.truth_status !== "CURRENT");
    const searchText = [deviceDisplayName(item, rooms), item.metadata.manufacturer, item.metadata.model, deviceRoom(item)?.name].filter(Boolean).join(" ").toLowerCase();
    return matchesFilter && searchText.includes(query.trim().toLowerCase()) && (roomFilter === "all" || deviceRoom(item)?.place_id === roomFilter);
  });
  const beginCommission = (item: ProviderDevice) => {
    setEditing(null);
    setCommissioningId(item.device_handle);
    setName(String(item.metadata.name_by_user ?? item.metadata.name ?? "New device"));
    setPlaceId(rooms[0]?.place_id ?? "");
  };
  const beginEdit = (item: ProviderDevice) => {
    const resourceId = String(item.metadata.canonical_target_id ?? "");
    const currentRoom = rooms.find((room) => room.devices.some((device) => device.device_id === resourceId));
    setCommissioningId(null);
    setEditing(item);
    setName(deviceDisplayName(item, rooms));
    setPlaceId(currentRoom?.place_id ?? rooms[0]?.place_id ?? "");
  };
  const saveDevice = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!resourceId) return;
    const renamed = await mutate("/api/v1/devices/rename", { resource_id: resourceId, name });
    if (renamed?.status !== "SUCCEEDED") return;
    const moved = await mutate("/api/v1/devices/reassign", { resource_id: resourceId, place_id: placeId });
    if (moved?.status === "SUCCEEDED") setEditing(null);
  };
  const resourceId = editing ? String(editing.metadata.canonical_target_id ?? "") : "";
  return <div className="dashboard">
    <Card title="Add a device"><p className="muted">Put your Zigbee device in pairing mode, open the window, then refresh.</p><div className="stack"><label>Pairing window (seconds)<input type="number" min="1" max="120" value={duration} onChange={(event) => setDuration(event.target.value)} /></label><div className="button-row"><button onClick={() => void mutate("/api/v1/devices/permit-pairing", { duration_seconds: Number(duration) })}>Open pairing window</button><button onClick={() => void mutate("/api/v1/devices/refresh")}>Refresh discovered devices</button></div></div></Card>
    <Card title="Discovered Home Assistant devices" className="device-catalog"><div className="filter-bar"><label>Search devices<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Name, model, or room" /></label><label>Device status<select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">All devices</option><option value="commissioned">Commissioned</option><option value="new">Needs a room</option><option value="attention">State needs attention</option></select></label><label>Filter by room<select value={roomFilter} onChange={(event) => setRoomFilter(event.target.value)}><option value="all">All rooms</option>{rooms.map((room) => <option key={room.place_id} value={room.place_id}>{room.name}</option>)}</select></label></div><p className="muted" role="status">{filtered.length} of {discovered.length} devices</p>{filtered.length ? <ul className="clean-list list-spaced device-grid">{filtered.map((item) => { const mapped = item.metadata.mapping_status === "MAPPED"; const resourceId = String(item.metadata.canonical_target_id ?? ""); const power = item.capabilities?.find((capability) => capability.type === "power.set" && capability.writable); const label = deviceDisplayName(item, rooms); const observed = item.observed_at ? new Date(item.observed_at).toLocaleString() : "No current observation"; return <li className="device-row" key={item.device_handle}><span><span className="device-icon"><Icon name={power ? "Power" : "Devices"} /></span><strong>{label}</strong><small className="muted">{deviceRoom(item)?.name ?? (mapped ? "No room assigned" : "Awaiting commissioning")}</small><small className="muted">{item.metadata.manufacturer ?? ""}{item.metadata.model ? ` · ${item.metadata.model}` : ""} · {mapped ? "Commissioned" : "Needs a room"}</small>{mapped && <small className="device-state">Current state: {["CURRENT", "CURRENT/KNOWN"].includes(item.truth_status ?? "") ? item.state ?? "UNKNOWN" : "UNKNOWN"}</small>}{mapped && <small className="muted">Truth: <StatusPill status={item.truth_status ?? "UNKNOWN"} /></small>}{mapped && <LastReported reading={item} />}{mapped && <small className="muted">Observed: {observed}</small>}{mapped && item.capabilities && item.capabilities.length > 0 && <CapabilityDetails capabilities={item.capabilities} label={label} />}</span><span className="button-row">{mapped && power && resourceId && <PowerControls id={resourceId} label={label} state={power.truth_status === "CURRENT" ? power.state : "UNKNOWN"} mutate={mutate} />}{mapped && <button type="button" disabled={!canonicalPlacement(item) || syncingId !== null} aria-describedby={!canonicalPlacement(item) ? `sync-mapping-${item.device_handle}` : undefined} onClick={() => void syncCapabilities(item)}><Icon name="Refresh" />{syncingId === item.device_handle ? "Syncing capabilities…" : "Sync capabilities"}</button>}{mapped && !canonicalPlacement(item) && <small className="muted" id={`sync-mapping-${item.device_handle}`}>Cannot sync: canonical device name or room mapping is missing or ambiguous. Refresh household data first.</small>}{mapped ? <button onClick={() => beginEdit(item)}>Manage</button> : <button onClick={() => beginCommission(item)}>Add to Anima</button>}</span></li>; })}</ul> : <p className="empty-state">{discovered.length ? "No devices match these filters." : "No discovered devices yet. Pair a device, then refresh."}</p>}
      {commissioningId && <form className="stack commission-form" onSubmit={(event) => { event.preventDefault(); void mutate("/api/v1/devices/commission", { device_handle: commissioningId, name, place_id: placeId }).then((result) => { if (result?.status === "SUCCEEDED") setCommissioningId(null); }); }}><h3>Place device in Anima</h3><label>Display name<input required maxLength={120} value={name} onChange={(event) => setName(event.target.value)} /></label><label>Room<select required value={placeId} onChange={(event) => setPlaceId(event.target.value)}><option value="" disabled>Select a room</option>{rooms.map((room) => <option key={room.place_id} value={room.place_id}>{room.name}</option>)}</select></label><div className="button-row"><button type="submit" disabled={!placeId}>Commission device</button><button type="button" onClick={() => setCommissioningId(null)}>Cancel</button></div></form>}
      {editing && <form className="stack commission-form" onSubmit={(event) => void saveDevice(event)}><h3>Manage commissioned device</h3><p className="muted">Update the Anima name and room. The provider registry is preserved.</p><label>Display name<input required maxLength={120} value={name} onChange={(event) => setName(event.target.value)} /></label><label>Room<select required value={placeId} onChange={(event) => setPlaceId(event.target.value)}><option value="" disabled>Select a room</option>{rooms.map((room) => <option key={room.place_id} value={room.place_id}>{room.name}</option>)}</select></label><div className="button-row"><button type="submit" disabled={!placeId || !resourceId}>Save device</button><button type="button" onClick={() => { if (resourceId) void mutate("/api/v1/devices/retire", { resource_id: resourceId }).then((result) => { if (result?.status === "SUCCEEDED") setEditing(null); }); }}>Remove from Anima</button><button type="button" onClick={() => setEditing(null)}>Cancel</button></div></form>}
    </Card>
  </div>;
}
function NotificationRoutesView({ routes, mutate }: { routes: NotificationRoute[]; mutate: (path: string, payload?: Record<string, unknown>) => Promise<MutationOutcome | null> }) {
  const current = routes[0];
  const [label, setLabel] = useState(current?.label ?? "Household notifications");
  const [minimumPriority, setMinimumPriority] = useState(current?.minimum_priority ?? 70);
  const [enabled, setEnabled] = useState(current?.enabled ?? true);
  useEffect(() => { setLabel(current?.label ?? "Household notifications"); setMinimumPriority(current?.minimum_priority ?? 70); setEnabled(current?.enabled ?? true); }, [current?.route_id, current?.version]);
  const save = async (event: React.FormEvent) => { event.preventDefault(); const payload: Record<string, unknown> = { label, minimum_priority: minimumPriority, enabled }; if (current) { payload.route_id = current.route_id; payload.expected_version = current.version; } await mutate("/api/v1/notifications/routes", payload); };
  const destinationLabel = current?.destination === "server_configured" ? "Server configured" : current?.destination ?? "Server configured";
  return <div className="dashboard notification-routes"><Card title="Notification route"><p className="muted">Set alert priority and enable your route. Credentials stay on the server.</p><form className="stack" onSubmit={(event) => void save(event)}><label>Route label<input required maxLength={80} value={label} onChange={(event) => setLabel(event.target.value)} /></label><label>Minimum alert priority<input required type="number" min="0" max="100" value={minimumPriority} onChange={(event) => setMinimumPriority(Number(event.target.value))} /></label><label className="checkbox"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /> Route enabled</label><button type="submit">{current ? "Save route" : "Create route"}</button></form></Card><Card title="Delivery boundary"><dl className="settings-grid"><dt>Provider</dt><dd><strong>{current?.provider ?? "ntfy"}</strong></dd><dt>Destination</dt><dd><strong>{destinationLabel}</strong></dd><dt>Status</dt><dd><StatusPill status={current ? (current.enabled ? "ACTIVE" : "DISABLED") : "NOT_CONFIGURED"} /></dd></dl><p className="muted">Provider acceptance does not confirm that someone received or read an alert.</p></Card></div>;
}

function AlertPoliciesView({ policies, devices, rooms, mutate, events, nextCursor, loading, loadOlder }: { policies: AlertPolicy[]; devices: ProviderDevice[]; rooms: Room[]; mutate: (path: string, payload?: Record<string, unknown>) => Promise<MutationOutcome | null>; events: AlertEvent[]; nextCursor: string | null; loading: boolean; loadOlder: () => Promise<void> }) {
  const resources = devices.filter((item) => item.present && item.metadata.canonical_target_id).map((item) => ({ id: String(item.metadata.canonical_target_id), label: deviceDisplayName(item, rooms) }));
  const blank: Omit<AlertPolicy, "policy_id" | "version"> = { event_type: "senseguard.event", timezone: "America/New_York", start_local: "00:00", end_local: "05:00", priority: 90, guaranteed_attention: true, delivery_mode: "SENTRY_COGNITION", enabled: true, resource_ids: resources[0] ? [resources[0].id] : [] };
  const [draft, setDraft] = useState(blank); const [editing, setEditing] = useState<AlertPolicy | null>(null);
  useEffect(() => { if (!editing && resources[0] && draft.resource_ids.length === 0) setDraft({ ...draft, resource_ids: [resources[0].id] }); }, [resources.length, editing]);
  const edit = (policy: AlertPolicy) => { setEditing(policy); setDraft({ event_type: policy.event_type, timezone: policy.timezone, start_local: policy.start_local.slice(0, 5), end_local: policy.end_local.slice(0, 5), priority: policy.priority, guaranteed_attention: policy.guaranteed_attention, delivery_mode: policy.delivery_mode, enabled: policy.enabled, resource_ids: policy.resource_ids }); };
  const reset = () => { setEditing(null); setDraft({ ...blank, resource_ids: resources[0] ? [resources[0].id] : [] }); };
  const save = async (event: React.FormEvent) => { event.preventDefault(); const payload: Record<string, unknown> = { ...draft }; if (editing) { payload.policy_id = editing.policy_id; payload.expected_version = editing.version; } const result = await mutate("/api/v1/alerts/policies", payload); if (result?.status === "SUCCEEDED") reset(); };
  const toggle = (policy: AlertPolicy) => void mutate("/api/v1/alerts/policies", { policy_id: policy.policy_id, expected_version: policy.version, resource_ids: policy.resource_ids, event_type: policy.event_type, timezone: policy.timezone, start_local: policy.start_local.slice(0, 5), end_local: policy.end_local.slice(0, 5), priority: policy.priority, guaranteed_attention: policy.guaranteed_attention, delivery_mode: policy.delivery_mode, enabled: !policy.enabled });
  return <div className="dashboard"><Card title={editing ? "Edit alert policy" : "Create an alert policy"}><p className="muted">Choose a resource, time window, priority, and delivery mode.</p>{resources.length ? <form className="stack" onSubmit={(event) => void save(event)}><label>SenseGuard resources<select multiple required value={draft.resource_ids} onChange={(event) => setDraft({ ...draft, resource_ids: Array.from(event.target.selectedOptions, (option) => option.value) })}>{resources.map((resource) => <option key={resource.id} value={resource.id}>{resource.label}</option>)}</select></label><label>Event type<input required maxLength={120} value={draft.event_type} onChange={(event) => setDraft({ ...draft, event_type: event.target.value })} /></label><div className="form-grid"><label>From<input required type="time" value={draft.start_local} onChange={(event) => setDraft({ ...draft, start_local: event.target.value })} /></label><label>Until<input required type="time" value={draft.end_local} onChange={(event) => setDraft({ ...draft, end_local: event.target.value })} /></label><label>Priority<input required type="number" min="0" max="100" value={draft.priority} onChange={(event) => setDraft({ ...draft, priority: Number(event.target.value) })} /></label><label>Timezone<input required maxLength={64} value={draft.timezone} onChange={(event) => setDraft({ ...draft, timezone: event.target.value })} /></label></div><label>Delivery<select value={draft.delivery_mode} onChange={(event) => setDraft({ ...draft, delivery_mode: event.target.value as AlertPolicy["delivery_mode"] })}><option value="SENTRY_COGNITION">SENTRY cognition</option><option value="NOTIFICATION">Notification</option></select></label><label className="checkbox"><input type="checkbox" checked={draft.guaranteed_attention} onChange={(event) => setDraft({ ...draft, guaranteed_attention: event.target.checked })} /> Guaranteed attention</label><label className="checkbox"><input type="checkbox" checked={draft.enabled} onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })} /> Enabled</label><div className="button-row"><button type="submit">{editing ? "Save changes" : "Create policy"}</button>{editing && <button type="button" onClick={reset}>Cancel</button>}</div></form> : <p className="muted">No canonical SenseGuard resources are commissioned yet. Add and commission a device first.</p>}</Card><Card title="Configured policies"><p className="muted">Disabling a policy preserves its history.</p>{policies.length ? <ul className="clean-list list-spaced">{policies.map((policy) => <li className="policy-row" key={policy.policy_id}><span><strong>{policy.event_type}</strong><small className="muted">{policy.start_local.slice(0, 5)}–{policy.end_local.slice(0, 5)} · priority {policy.priority} · v{policy.version}</small></span><span className="button-row"><StatusPill status={policy.enabled ? "ACTIVE" : "DISABLED"} /><button onClick={() => edit(policy)}>Edit</button><button aria-pressed={policy.enabled} onClick={() => toggle(policy)}>{policy.enabled ? "Disable" : "Enable"}</button></span></li>)}</ul> : <p className="muted">No alert policies configured.</p>}</Card><Card title="Alert inbox"><p className="muted">Recorded SenseGuard events. Delivery status does not confirm human receipt.</p>{events.length ? <ul className="clean-list list-spaced">{events.map((event) => <li className="alert-row" key={event.alert_id}><span><strong>{event.resource_name}</strong><small className="muted">{event.event_type} · {new Date(event.occurred_at).toLocaleString()} · priority {event.priority}</small><small className="muted">{event.delivery_mode.replaceAll("_", " ")}</small></span><span className="button-row"><StatusPill status={event.delivery_status} /></span></li>)}</ul> : <p className="muted">No matched SenseGuard events recorded yet.</p>}{nextCursor && <div className="button-row"><button type="button" onClick={() => void loadOlder()} disabled={loading}>{loading ? "Loading older alerts…" : "Load older alerts"}</button></div>}</Card></div>;
}
function inputDate(value: string) { const date = new Date(value); const offset = date.getTimezoneOffset() * 60_000; return new Date(date.getTime() - offset).toISOString().slice(0, 16); }
function TaskCalendar({ mutate }: { mutate: (path: string, payload?: Record<string, unknown>) => Promise<MutationOutcome | null> }) {
  const [title, setTitle] = useState(""); const [when, setWhen] = useState(""); const [note, setNote] = useState(""); const [eventTitle, setEventTitle] = useState(""); const [start, setStart] = useState(""); const [end, setEnd] = useState(""); const [editing, setEditing] = useState<string | null>(null); const [editTitle, setEditTitle] = useState(""); const [editStart, setEditStart] = useState(""); const [editEnd, setEditEnd] = useState("");
  const [tasks, setTasks] = useState<Task[]>([]); const [calendar, setCalendar] = useState<CalendarEvent[]>([]);
  const [readError, setReadError] = useState("");
  const readGeneration = useRef(0);
  const reload = async () => { const generation = ++readGeneration.current; const [taskItems, calendarItems] = await Promise.all([allPages<Task>("/api/v1/tasks"), allPages<CalendarEvent>("/api/v1/calendar")]); if (generation !== readGeneration.current) return; setTasks(taskItems); setCalendar(calendarItems); };
  useEffect(() => { void reload(); }, []);
  const runMutation = async (path: string, payload?: Record<string, unknown>) => {
    const result = await mutate(path, payload);
    const event = (result?.result as { event?: CalendarEvent } | null)?.event;
    if (result?.status === "SUCCEEDED" && path.startsWith("/api/v1/calendar") && event && typeof event.event_id === "string" && typeof event.title === "string" && typeof event.start_at === "string" && typeof event.end_at === "string" && typeof event.version === "number" && typeof event.status === "string") {
      // Core returns the authoritative saved row; do not gate it on an unrelated task read.
      readGeneration.current += 1;
      setCalendar((current) => [...current.filter((item) => item.event_id !== event.event_id), event].sort((a, b) => a.start_at.localeCompare(b.start_at)));
      setReadError("");
      void reload().catch(() => setReadError("Task/calendar refresh failed. Showing the last confirmed data; reopen Tasks & Calendar to refresh."));
      return result;
    }
    await reload(); return result;
  };
  const edit = (event: CalendarEvent) => { setEditing(event.event_id); setEditTitle(event.title); setEditStart(inputDate(event.start_at)); setEditEnd(inputDate(event.end_at)); };
  return <div className="dashboard">{readError && <div className="notice error" role="alert">{readError}</div>}<Card title="Tasks"><form className="stack" onSubmit={(event) => { event.preventDefault(); void runMutation("/api/v1/tasks", { title, when, note }).then((result) => { if (result?.status === "SUCCEEDED") { setTitle(""); setWhen(""); setNote(""); } }); }}><label>Reminder title<input required value={title} onChange={(event) => setTitle(event.target.value)} /></label><label>When<input required type="datetime-local" value={when} onChange={(event) => setWhen(event.target.value)} /></label><label>Note<input value={note} onChange={(event) => setNote(event.target.value)} /></label><button type="submit">Create task</button></form><ul className="clean-list list-spaced">{tasks.map((task) => <li key={task.task_id}><span>{task.title}<small className="muted">{task.next_run_at ? new Date(task.next_run_at).toLocaleString() : ""}</small></span><span className="button-row"><StatusPill status={task.status} />{task.status === "ACTIVE" && <><button onClick={() => void runMutation(`/api/v1/tasks/${task.task_id}/pause`)}>Pause</button><button onClick={() => void runMutation(`/api/v1/tasks/${task.task_id}/cancel`)}>Cancel</button></>}{task.status === "PAUSED" && <><button onClick={() => void runMutation(`/api/v1/tasks/${task.task_id}/resume`)}>Resume</button><button onClick={() => void runMutation(`/api/v1/tasks/${task.task_id}/cancel`)}>Cancel</button></>}</span></li>)}</ul></Card><Card title="Calendar"><form className="stack" onSubmit={(event) => { event.preventDefault(); void runMutation("/api/v1/calendar", { title: eventTitle, start_at: new Date(start).toISOString(), end_at: new Date(end).toISOString(), timezone: "UTC" }).then((result) => { if (result?.status === "SUCCEEDED") { setEventTitle(""); setStart(""); setEnd(""); } }); }}><label>Event title<input required value={eventTitle} onChange={(event) => setEventTitle(event.target.value)} /></label><label>Starts<input required type="datetime-local" value={start} onChange={(event) => setStart(event.target.value)} /></label><label>Ends<input required type="datetime-local" value={end} onChange={(event) => setEnd(event.target.value)} /></label><button type="submit">Create event</button></form><ul className="clean-list list-spaced">{calendar.map((event) => <li className="calendar-row" key={event.event_id}>{editing === event.event_id ? <form className="edit-form" onSubmit={(submit) => { submit.preventDefault(); void runMutation(`/api/v1/calendar/${event.event_id}/update`, { expected_version: event.version ?? 1, title: editTitle, start_at: new Date(editStart).toISOString(), end_at: new Date(editEnd).toISOString(), timezone: "UTC" }).then((result) => { if (result?.status === "SUCCEEDED") setEditing(null); }); }}><label>Title<input required value={editTitle} onChange={(input) => setEditTitle(input.target.value)} /></label><label>Starts<input required type="datetime-local" value={editStart} onChange={(input) => setEditStart(input.target.value)} /></label><label>Ends<input required type="datetime-local" value={editEnd} onChange={(input) => setEditEnd(input.target.value)} /></label><span className="button-row"><button type="submit">Save edit</button><button type="button" onClick={() => setEditing(null)}>Close</button></span></form> : <><span>{event.title}<small className="muted">{new Date(event.start_at).toLocaleString()}</small></span><span className="button-row"><StatusPill status={event.status} />{event.status === "ACTIVE" && <><button onClick={() => edit(event)}>Edit</button><button onClick={() => void runMutation(`/api/v1/calendar/${event.event_id}/cancel`, { expected_version: event.version ?? 1 })}>Cancel</button></>}</span></>}</li>)}</ul></Card></div>;
}
function SettingsPanel({ value, voice, csrf, onSaved, onVoiceSaved, setError, setOutcome }: { value: Settings; voice: SentryVoiceSettings | null; csrf: string; onSaved: (value: Settings) => void; onVoiceSaved: (value: SentryVoiceSettings) => void; setError: (value: string) => void; setOutcome: (value: MutationOutcome) => void }) {
  const [draft, setDraft] = useState(value); useEffect(() => setDraft(value), [value]); const update = <K extends keyof Settings>(key: K, next: Settings[K]) => setDraft({ ...draft, [key]: next }); const toggleWidget = (id: string) => update("visible_widgets", draft.visible_widgets.includes(id) ? draft.visible_widgets.filter((item) => item !== id) : [...draft.visible_widgets, id]); const moveWidget = (id: string, direction: -1 | 1) => { const order = [...draft.widget_order]; const index = order.indexOf(id); const next = index + direction; if (index < 0 || next < 0 || next >= order.length) return; [order[index], order[next]] = [order[next], order[index]]; update("widget_order", order); };
  const save = async () => { try { const result = await api<{ settings: Settings }>("/api/v1/settings", { method: "PUT", body: JSON.stringify({ payload: draft }), headers: { "Content-Type": "application/json", "X-Anima-CSRF": csrf, Origin: window.location.origin } }); onSaved(result.settings); setOutcome({ status: "SUCCEEDED", operation: "settings.update", detail: "Preferences saved" }); setError(""); } catch (err) { setError(err instanceof Error ? err.message : "Settings could not be saved"); } }; const widgets = ["status", "presence", "weather", "agenda", "tasks", "controls", "conversation", "activity", "household", "reports", "health"];
  const [voiceDraft, setVoiceDraft] = useState(voice || { voice_id: "bm_george", speech_speed: 0.9, sleep_enabled: false }); useEffect(() => { if (voice) setVoiceDraft(voice); }, [voice]);
  const saveVoice = async () => { try { const result = await api<{ status: string; settings: SentryVoiceSettings }>("/api/v1/sentry/voice-settings", { method: "PUT", body: JSON.stringify({ payload: voiceDraft }), headers: { "Content-Type": "application/json", "X-Anima-CSRF": csrf, Origin: window.location.origin } }); onVoiceSaved(result.settings); setOutcome({ status: "SUCCEEDED", operation: "sentry.voice-settings.update", detail: "SENTRY voice settings saved in ANIMA" }); } catch (err) { setError(err instanceof Error ? err.message : "SENTRY voice settings could not be saved"); } };
  return <><Card title="Household interface"><p className="muted">Personalize appearance, layout, and accessibility.</p><div className="settings-form"><label>Appearance<select value={draft.appearance} onChange={(event) => update("appearance", event.target.value as Settings["appearance"])}><option value="system">System</option><option value="light">Light</option><option value="night">Night</option></select></label><label>Accent<select value={draft.accent} onChange={(event) => update("accent", event.target.value as Settings["accent"])}><option value="purple">Neon purple</option><option value="ember">Ember</option><option value="sage">Sage</option><option value="sky">Sky</option></select></label><label>Density<select value={draft.density} onChange={(event) => update("density", event.target.value as Settings["density"])}><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></label><label>Text scale<select value={draft.text_scale} onChange={(event) => update("text_scale", event.target.value as Settings["text_scale"])}><option value="small">Small</option><option value="normal">Normal</option><option value="large">Large</option></select></label><label>Layout profile<select value={draft.display_mode} onChange={(event) => update("display_mode", event.target.value as Settings["display_mode"])}><option value="wall">Wall</option><option value="tablet">Tablet</option><option value="phone">Phone</option><option value="desktop">Desktop</option></select></label><label className="checkbox"><input type="checkbox" checked={draft.reduced_motion} onChange={(event) => update("reduced_motion", event.target.checked)} /> Reduce motion</label></div><fieldset className="widget-settings"><legend>Home widgets</legend>{widgets.map((id) => { const index = draft.widget_order.indexOf(id); return <label className="widget-setting" key={id}><input type="checkbox" checked={draft.visible_widgets.includes(id)} onChange={() => toggleWidget(id)} /><span>{id}</span><button type="button" aria-label={`Move ${id} up`} disabled={index <= 0} onClick={() => moveWidget(id, -1)}>↑</button><button type="button" aria-label={`Move ${id} down`} disabled={index < 0 || index >= draft.widget_order.length - 1} onClick={() => moveWidget(id, 1)}>↓</button></label>; })}</fieldset><button onClick={() => void save()}>Save preferences</button></Card><Card title="SENTRY voice"><p className="muted">ANIMA owns voice and wake availability for the active SENTRY projection.</p><div className="settings-form"><label>Voice<select value={voiceDraft.voice_id} onChange={event => setVoiceDraft({ ...voiceDraft, voice_id: event.target.value })}><option value="bm_george">George</option><option value="bm_lewis">Lewis</option><option value="am_adam">Adam</option><option value="am_michael">Michael</option><option value="af_bella">Bella</option><option value="af_sarah">Sarah</option><option value="bf_emma">Emma</option><option value="bf_isabella">Isabella</option></select></label><label>Speech speed<input type="range" min="0.75" max="1.30" step="0.05" value={voiceDraft.speech_speed} onChange={event => setVoiceDraft({ ...voiceDraft, speech_speed: Number(event.target.value) })} /><output>{voiceDraft.speech_speed.toFixed(2)}×</output></label><label className="checkbox"><input type="checkbox" checked={voiceDraft.sleep_enabled} onChange={event => setVoiceDraft({ ...voiceDraft, sleep_enabled: event.target.checked })} /> Sleep mode</label></div><p className="muted">Off means standby: SENTRY remains available for wake-word listening. Changes apply to the active living-room projection through the ANIMA bridge.</p><button onClick={() => void saveVoice()}>Save SENTRY voice and mode</button></Card></>;
}
function ScenesView({ scenes, controls, mutate }: { scenes: Scene[]; controls: Home["controls"]; mutate: (path: string, payload?: Record<string, unknown>) => Promise<MutationOutcome | null> }) {
  const [name, setName] = useState(""); const [resourceId, setResourceId] = useState(controls[0]?.control_id ?? ""); const [desiredOn, setDesiredOn] = useState(true); const [steps, setSteps] = useState<SceneStep[]>([]); const [editing, setEditing] = useState<Scene | null>(null);
  const reset = () => { setEditing(null); setName(""); setSteps([]); setResourceId(controls[0]?.control_id ?? ""); setDesiredOn(true); };
  const beginEdit = (scene: Scene) => { setEditing(scene); setName(scene.name); setSteps(scene.steps); };
  const addStep = () => { if (!resourceId || steps.some((step) => step.resource_id === resourceId)) return; setSteps([...steps, { resource_id: resourceId, desired_on: desiredOn }]); };
  const save = async (event: React.FormEvent) => { event.preventDefault(); if (!steps.length) return; const payload: Record<string, unknown> = { name, steps, enabled: editing?.enabled ?? true }; if (editing) { payload.scene_id = editing.scene_id; payload.expected_version = editing.version; } const result = await mutate("/api/v1/scenes", payload); if (result?.status === "SUCCEEDED") reset(); };
  return <div className="dashboard"><Card title={editing ? "Edit scene" : "Create a scene"}><p className="muted">Choose device states. Each applied step is authorized and verified.</p>{controls.length ? <form className="stack" onSubmit={(event) => void save(event)}><label>Scene name<input required maxLength={80} value={name} onChange={(event) => setName(event.target.value)} /></label><div className="form-grid"><label>Device<select value={resourceId} onChange={(event) => setResourceId(event.target.value)}>{controls.map((control) => <option key={control.control_id} value={control.control_id}>{control.label}</option>)}</select></label><label>State<select value={desiredOn ? "on" : "off"} onChange={(event) => setDesiredOn(event.target.value === "on")}><option value="on">On</option><option value="off">Off</option></select></label></div><button type="button" onClick={addStep} disabled={!resourceId || steps.some((step) => step.resource_id === resourceId)}>Add step</button>{steps.length ? <ol className="clean-list list-spaced">{steps.map((step, index) => <li key={step.resource_id}><span>{controls.find((control) => control.control_id === step.resource_id)?.label ?? step.resource_id}<small className="muted">{step.desired_on ? "On" : "Off"}</small></span><button type="button" onClick={() => setSteps(steps.filter((_, itemIndex) => itemIndex !== index))}>Remove</button></li>)}</ol> : <p className="muted">Add at least one commissioned power device.</p>}<div className="button-row"><button type="submit" disabled={!name.trim() || !steps.length}>{editing ? "Save scene" : "Create scene"}</button>{editing && <button type="button" onClick={reset}>Cancel</button>}</div></form> : <p className="muted">No commissioned power devices are available yet.</p>}</Card><Card title="Saved scenes"><p className="muted">Apply a scene to run its saved steps. Partial results are reported.</p>{scenes.length ? <ul className="clean-list list-spaced">{scenes.map((scene) => <li className="integration-row" key={scene.scene_id}><span><strong>{scene.name}</strong><small className="muted">{scene.steps.length} step(s) · v{scene.version} · {scene.enabled ? "enabled" : "disabled"}</small></span><span className="button-row"><button disabled={!scene.enabled} onClick={() => void mutate(`/api/v1/scenes/${scene.scene_id}/apply`)}>Apply</button><button onClick={() => beginEdit(scene)}>Edit</button></span></li>)}</ul> : <p className="muted">No scenes configured.</p>}</Card></div>;
}
function AutomationsView({ automations, devices, controls, mutate }: { automations: Automation[]; devices: ProviderDevice[]; controls: Home["controls"]; mutate: (path: string, payload?: Record<string, unknown>) => Promise<MutationOutcome | null> }) {
  const mapped = devices.filter((item) => item.metadata.mapping_status === "MAPPED" && item.metadata.canonical_target_id);
  const [name, setName] = useState(""); const [triggerId, setTriggerId] = useState(mapped[0]?.metadata.canonical_target_id ?? ""); const [triggerState, setTriggerState] = useState<"on" | "off">("on"); const [actionId, setActionId] = useState(controls[0]?.control_id ?? ""); const [actionOn, setActionOn] = useState(true); const [enabled, setEnabled] = useState(true); const [editing, setEditing] = useState<Automation | null>(null);
  const reset = () => { setEditing(null); setName(""); setTriggerId(mapped[0]?.metadata.canonical_target_id ?? ""); setTriggerState("on"); setActionId(controls[0]?.control_id ?? ""); setActionOn(true); setEnabled(true); };
  const beginEdit = (item: Automation) => { setEditing(item); setName(item.name); setTriggerId(item.trigger_resource_id); setTriggerState(item.trigger_state); setActionId(item.action_resource_id); setActionOn(item.action_desired_on); setEnabled(item.enabled); };
  const save = async (event: React.FormEvent) => { event.preventDefault(); const payload: Record<string, unknown> = { name, trigger_resource_id: triggerId, trigger_state: triggerState, action_resource_id: actionId, action_desired_on: actionOn, enabled }; if (editing) { payload.automation_id = editing.automation_id; payload.expected_version = editing.version; } const result = await mutate("/api/v1/automations", payload); if (result?.status === "SUCCEEDED") reset(); };
  const label = (id: string) => controls.find((item) => item.control_id === id)?.label ?? mapped.find((item) => item.metadata.canonical_target_id === id)?.metadata.name ?? "Unnamed device";
  return <div className="dashboard"><Card title={editing ? "Edit automation" : "Create an automation"}><p className="muted">Choose a device change and a power action. Each action is authorized and verified.</p>{mapped.length && controls.length ? <form className="stack" onSubmit={(event) => void save(event)}><label>Name<input required maxLength={80} value={name} onChange={(event) => setName(event.target.value)} /></label><div className="form-grid"><label>When this device is<select value={triggerId} onChange={(event) => setTriggerId(event.target.value)}>{mapped.map((item) => <option key={item.metadata.canonical_target_id ?? item.device_handle} value={item.metadata.canonical_target_id ?? ""}>{label(item.metadata.canonical_target_id ?? "")}</option>)}</select></label><label>State<select value={triggerState} onChange={(event) => setTriggerState(event.target.value as "on" | "off")}><option value="on">On</option><option value="off">Off</option></select></label><label>Then control<select value={actionId} onChange={(event) => setActionId(event.target.value)}>{controls.map((item) => <option key={item.control_id} value={item.control_id}>{item.label}</option>)}</select></label><label>Set state<select value={actionOn ? "on" : "off"} onChange={(event) => setActionOn(event.target.value === "on")}><option value="on">On</option><option value="off">Off</option></select></label></div><label className="checkbox"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /> Automation enabled</label><div className="button-row"><button type="submit" disabled={!name.trim() || !triggerId || !actionId}>{editing ? "Save automation" : "Create automation"}</button>{editing && <button type="button" onClick={reset}>Cancel</button>}</div></form> : <p className="muted">Commission at least one device and one power control before creating an automation.</p>}</Card><Card title="Saved automations"><p className="muted">Enable a rule to respond to matching device observations.</p>{automations.length ? <ul className="clean-list list-spaced">{automations.map((item) => <li className="integration-row" key={item.automation_id}><span><strong>{item.name}</strong><small className="muted">When {label(item.trigger_resource_id)} is {item.trigger_state}, set {label(item.action_resource_id)} {item.action_desired_on ? "on" : "off"} · v{item.version}</small></span><span className="button-row"><StatusPill status={item.enabled ? "ACTIVE" : "DISABLED"} /><button aria-pressed={item.enabled} onClick={() => void mutate("/api/v1/automations", { automation_id: item.automation_id, expected_version: item.version, name: item.name, trigger_resource_id: item.trigger_resource_id, trigger_state: item.trigger_state, action_resource_id: item.action_resource_id, action_desired_on: item.action_desired_on, enabled: !item.enabled })}>{item.enabled ? "Disable" : "Enable"}</button><button onClick={() => beginEdit(item)}>Edit</button></span></li>)}</ul> : <p className="muted">No automations configured.</p>}</Card></div>;
}
function Capabilities({ items }: { items: Capability[] }) {
  const [query, setQuery] = useState("");
  const filtered = items.filter((item) => item.label.toLowerCase().includes(query.trim().toLowerCase()));
  const stateCounts = Object.entries(items.reduce<Record<string, number>>((counts, item) => { counts[item.state] = (counts[item.state] ?? 0) + 1; return counts; }, {}));
  return <div className="dashboard"><Card title="Capability availability"><div className="overview-meters">{stateCounts.map(([state, count]) => <Meter key={state} value={count} max={items.length} label={state.replaceAll("_", " ")} />)}</div>{!items.length && <p className="empty-state">No capabilities registered.</p>}</Card><Card title="Capabilities"><label className="filter-bar">Search capabilities<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} /></label><ul className="clean-list">{filtered.map((item) => <li key={item.id}><Icon name="Capabilities" /><span>{item.label}{item.detail && <details className="integration-details"><summary>Details</summary><small className="muted">{item.detail}</small></details>}</span><StatusPill status={item.state} /></li>)}</ul>{!filtered.length && items.length > 0 && <p className="empty-state">No matching capabilities.</p>}</Card></div>;
}
function BackupsView({ backups, mutate }: { backups: BackupRecord[]; mutate: (path: string, payload?: Record<string, unknown>) => Promise<MutationOutcome | null> }) {
  const restore = async (backup: BackupRecord) => {
    const confirmed = window.confirm("Restore this ANIMA snapshot? Current household records will be replaced, and device state will require fresh Home Assistant observation.");
    if (confirmed) await mutate("/api/v1/backups/restore", { backup_id: backup.backup_id, confirm: true });
  };
  return <div className="dashboard"><Card title="ANIMA backups"><p className="muted">Create, validate, or restore a household snapshot. Archives and credentials stay on the server.</p><div className="button-row"><button onClick={() => void mutate("/api/v1/backups/create")}>Create backup</button></div>{backups.length ? <ul className="clean-list list-spaced">{backups.map((backup) => <li className="integration-row" key={backup.backup_id}><span><strong>{new Date(backup.captured_at).toLocaleString()}</strong><small className="muted">{backup.backup_id} · {Math.round(backup.size_bytes / 1024)} KiB · SHA-256 {backup.sha256.slice(0, 12)}…</small></span><span className="button-row"><StatusPill status={backup.restorable ? "VALID" : "INVALID"} /><button onClick={() => void mutate("/api/v1/backups/inspect", { backup_id: backup.backup_id })}>Validate</button><button disabled={!backup.restorable} onClick={() => void restore(backup)}>Restore</button></span></li>)}</ul> : <p className="muted">No server-owned snapshots are available for this household.</p>}</Card><Card title="Recovery boundary"><dl className="settings-grid"><dt>Storage</dt><dd><strong>ANIMA server</strong></dd><dt>Content</dt><dd><strong>PostgreSQL archive</strong></dd><dt>Restore</dt><dd><strong>Explicit owner confirmation</strong></dd><dt>After restore</dt><dd><strong>Physical state unknown until reobserved</strong></dd></dl><p className="muted">After restoring, refresh Home Assistant observations before relying on device state.</p></Card></div>;
}
function zhaSetupFrom(outcome: MutationOutcome | null): ZHASetup | null {
  if (!outcome || !outcome.result || typeof outcome.result !== "object") return null;
  const value = outcome.result as { state?: unknown; setup_id?: unknown; step_id?: unknown; fields?: unknown };
  if (value.state !== "AWAITING_INPUT" || typeof value.setup_id !== "string" || typeof value.step_id !== "string" || !Array.isArray(value.fields)) return null;
  return { setup_id: value.setup_id, step_id: value.step_id, fields: value.fields as ZHASetupField[] };
}
function ManagedIntegrationsView({ items, mutate }: { items: Integration[]; mutate: (path: string, payload?: Record<string, unknown>) => Promise<MutationOutcome | null> }) {
  const [setup, setSetup] = useState<ZHASetup | null>(null);
  const [input, setInput] = useState<Record<string, string>>({});
  const ha = items.find((item) => item.plugin_id === "anima.provider.home-assistant");
  const start = async () => { const result = await mutate("/api/v1/integrations/setup-zha"); const next = zhaSetupFrom(result); if (next) { setSetup(next); setInput({}); } };
  const continueSetup = async (event: React.FormEvent) => { event.preventDefault(); if (!setup) return; const result = await mutate("/api/v1/integrations/continue-zha", { setup_id: setup.setup_id, user_input: input }); const next = zhaSetupFrom(result); if (next) { setSetup(next); setInput({}); } else if (result?.status === "SUCCEEDED" || result?.status === "FAILED") setSetup(null); };
  const fieldLabel = (name: string) => ({ device_path: "Radio device path", radio_type: "Radio type", baudrate: "Baud rate", flow_control: "Flow control" }[name] ?? name);
  return <div className="dashboard"><Card title="Registered integrations"><p className="muted">Manage connected services. Credentials stay on the server.</p>{items.length ? <ul className="clean-list list-spaced">{items.map((item) => { const health = item.health; const status = health?.health ?? (item.state === "HEALTHY" ? "AVAILABLE" : item.state); return <li className="integration-row" key={item.plugin_id}><span><strong>{item.name}</strong><small className="muted">{item.description}</small><small className="muted">{item.capabilities.join(" · ")}</small>{health && <small className="muted">{health.health ?? item.state} · HA {health.connected_version ?? "version unknown"} · {health.mapped_count ?? 0} mapped / {health.unmapped_count ?? 0} awaiting commissioning{health.last_error_category ? ` · ${health.last_error_category}` : ""}</small>}</span><span className="button-row"><StatusPill status={status} />{item.plugin_id === "anima.provider.home-assistant" && item.enabled && <button onClick={() => void mutate("/api/v1/integrations/reconnect", { plugin_id: item.plugin_id })}>Reconnect</button>}{item.manageable && <button aria-pressed={item.enabled} onClick={() => void mutate("/api/v1/integrations/set-enabled", { plugin_id: item.plugin_id, enabled: !item.enabled })}>{item.enabled ? "Disable" : "Enable"}</button>}</span></li>; })}</ul> : <p className="muted">No Core-registered optional integrations are available.</p>}</Card><Card title="Add a supported integration"><p className="muted">Set up a Zigbee radio through your connected Home Assistant. ZHA is the supported setup flow.</p><div className="button-row"><button disabled={!ha?.enabled || Boolean(setup)} onClick={() => void start()}>Set up ZHA</button></div>{setup && <form className="stack setup-form" onSubmit={(event) => void continueSetup(event)}><h3>ZHA setup · {setup.step_id.replaceAll("_", " ")}</h3>{setup.fields.map((field) => <label key={field.name}>{fieldLabel(field.name)}{field.options?.length ? <select required={field.required} value={input[field.name] ?? ""} onChange={(event) => setInput({ ...input, [field.name]: event.target.value })}><option value="">Select…</option>{field.options.map((option) => <option key={option} value={option}>{option}</option>)}</select> : <input required={field.required} type={field.type === "integer" ? "number" : "text"} value={input[field.name] ?? ""} onChange={(event) => setInput({ ...input, [field.name]: event.target.value })} />}</label>)}<div className="button-row"><button type="submit">Continue setup</button><button type="button" onClick={() => setSetup(null)}>Cancel</button></div></form>}</Card><Card title="Boundary"><dl className="settings-grid"><dt>Authority</dt><dd><strong>ANIMA Core</strong></dd><dt>Configuration</dt><dd><strong>Server-owned</strong></dd><dt>Provider credentials</dt><dd><strong>Never shown here</strong></dd><dt>Supported setup</dt><dd><strong>ZHA only</strong></dd></dl><p className="muted">Home Assistant sign-in is used for connection setup. Integration management stays here.</p></Card></div>;
}
createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
