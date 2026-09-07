import { useEffect, useRef, useState } from "react";
import { Icon } from "./visuals";
import "./VendorConnectionsPanel.css";

export type VendorName = "tapo" | "wansview";
export type VendorConnectionState = "DISABLED" | "WAITING_APP_SETUP" | "SETUP_REQUIRED" | "READY" | "RECEIVED";
export type VendorConnectionStatus = {
  vendor: VendorName;
  configured: boolean;
  enabled: boolean;
  state: VendorConnectionState;
  gates: string[];
  last_receipt_at: string | null;
};
export type VendorConnectionsStatus = {
  configured: boolean;
  enabled: boolean;
  state: VendorConnectionState;
  gates: string[];
  vendors: VendorConnectionStatus[];
};
export type VendorConnectionsPanelProps = { onAuthFailure: () => void };

const endpoint = "/api/v1/vendor-events/status";
const names: VendorName[] = ["tapo", "wansview"];
const titles: Record<VendorName, string> = { tapo: "Tapo DL110", wansview: "Wansview" };
const states: VendorConnectionState[] = ["DISABLED", "WAITING_APP_SETUP", "SETUP_REQUIRED", "READY", "RECEIVED"];
const labels: Record<VendorConnectionState, string> = {
  DISABLED: "Disabled", WAITING_APP_SETUP: "Waiting for app setup", SETUP_REQUIRED: "Setup required",
  READY: "Ready to receive", RECEIVED: "Event received",
};
const gateLabels: Record<string, string> = {
  LIVE_FORMAT_UNQUALIFIED: "Live notification format needs qualification",
  PRODUCER_UNQUALIFIED: "Notification source needs qualification",
  WAITING_APP_SETUP: "Official app setup is pending",
  SOURCE_PRIVACY_UNQUALIFIED: "Vendor-only filtering and field minimization need verification",
  CANONICAL_MAPPING_REQUIRED: "Camera must be mapped to a canonical household resource",
  RELAY_DISABLED: "Notification relay is disabled",
  HA_LOCK_MAPPING_REQUIRED: "Verified Home Assistant lock mapping is required",
  SOURCE_SAMPLE_REQUIRED: "A genuine source sample is required",
};
const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const gateList = (value: unknown): value is string[] => Array.isArray(value) && value.length <= 16 && value.every(item => typeof item === "string" && item.length <= 160);
const timestamp = (value: unknown): value is string => typeof value === "string" && value.length <= 40
  && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)$/.test(value)
  && Number.isFinite(Date.parse(value));

// Copy only this status contract. Never render arbitrary errors, notification text,
// IDs, tokens, provider URLs, or fields added to a future response.
function parseStatus(value: unknown): VendorConnectionsStatus {
  if (!object(value) || typeof value.configured !== "boolean" || typeof value.enabled !== "boolean"
    || !states.includes(value.state as VendorConnectionState) || !gateList(value.gates) || !Array.isArray(value.vendors)
    || value.vendors.length > 2) throw new Error("INVALID_STATUS");
  const vendors: VendorConnectionStatus[] = [];
  for (const item of value.vendors) {
    if (!object(item) || !names.includes(item.vendor as VendorName) || vendors.some(row => row.vendor === item.vendor)
      || typeof item.configured !== "boolean" || typeof item.enabled !== "boolean"
      || !states.includes(item.state as VendorConnectionState) || !gateList(item.gates)
      || (item.last_receipt_at !== null && !timestamp(item.last_receipt_at))) throw new Error("INVALID_STATUS");
    vendors.push({ vendor: item.vendor as VendorName, configured: item.configured, enabled: item.enabled,
      state: item.state as VendorConnectionState, gates: [...item.gates], last_receipt_at: item.last_receipt_at as string | null });
  }
  return { configured: value.configured, enabled: value.enabled, state: value.state as VendorConnectionState,
    gates: [...value.gates], vendors };
}

function displayState(row: VendorConnectionStatus, globalEnabled: boolean): VendorConnectionState | null {
  if (row.state === "WAITING_APP_SETUP") return row.state;
  if (!globalEnabled || !row.enabled) return "DISABLED";
  if (!row.configured) return "SETUP_REQUIRED";
  if (row.state === "RECEIVED" && !row.last_receipt_at) return null;
  if (row.state === "READY" && row.gates.length) return "SETUP_REQUIRED";
  return row.state;
}

function Readiness({ label, value, yes, no }: { label: string; value: boolean | null; yes: string; no: string }) {
  return <li className={value === true ? "vendor-step-confirmed" : ""}>
    <Icon name={value === true ? "Check" : value === false ? "Pause" : "Info"} size={18} />
    <span>{label}</span><strong>{value === null ? "Not reported" : value ? yes : no}</strong>
  </li>;
}

function VendorCard({ vendor, row, globalEnabled, loading }: {
  vendor: VendorName; row: VendorConnectionStatus | undefined; globalEnabled: boolean; loading: boolean;
}) {
  const state = row ? displayState(row, globalEnabled) : null;
  const receipt = row?.last_receipt_at ?? null;
  const title = titles[vendor];
  const nextStep = !row ? "Refresh status to check which setup steps are available."
    : vendor === "tapo" && row.gates.includes("HA_LOCK_MAPPING_REQUIRED") ? "Have the administrator verify the actual HA lock source and its household mapping. No lock connection is established here."
    : state === "WAITING_APP_SETUP" ? `Complete the ${vendor === "tapo" ? "lock" : "camera"} setup in its official app first.`
    : !row.configured ? "An administrator needs to configure the private notification relay."
    : !row.enabled || !globalEnabled ? "Intake is disabled. Have the administrator review the setup gates before enabling it."
    : state === "RECEIVED" ? "Compare the recorded receipt with the actual app notification. Delivery beyond ANIMA is not verified here."
    : state === "READY" ? "Wait for a genuine app notification, then refresh to check its receipt."
    : "Review the setup checklist with the administrator before relying on notifications.";
  return <article className="card vendor-card" aria-labelledby={`vendor-${vendor}-title`}>
    <header className="vendor-card-heading"><span className="vendor-symbol"><Icon name={vendor === "tapo" ? "Lock" : "Notifications"} size={25} /></span>
      <div><h3 id={`vendor-${vendor}-title`}>{title}</h3><p>{vendor === "tapo" ? "Passive lock event observations" : "Motion notifications · no video"}</p></div>
    </header>
    <p className={`vendor-state vendor-state-${state?.toLowerCase() ?? "unknown"}`}>
      <Icon name={state === "RECEIVED" ? "Check" : state === "READY" ? "Clock" : "Info"} size={17} />
      {state ? labels[state] : loading ? "Checking status…" : "Status unavailable"}
    </p>
    <ul className="vendor-readiness" aria-label={`${title} readiness`}>
      <Readiness label="ANIMA configuration" value={row?.configured ?? null} yes="Configured" no="Not configured" />
      <Readiness label="Notification intake" value={row ? row.enabled && globalEnabled : null} yes="Enabled" no="Disabled" />
      <Readiness label="Event receipt" value={row ? Boolean(receipt) : null} yes="Recorded" no="None recorded" />
    </ul>
    <div className="vendor-receipt"><Icon name="Clock" size={18} /><div><strong>Last receipt in ANIMA</strong>
      {receipt ? <time dateTime={receipt} title={receipt}>{new Date(receipt).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "long" })}</time>
        : <span>{row ? "No receipt recorded" : "Not reported"}</span>}
    </div></div>
    <p className="vendor-next"><strong>Next step</strong>{nextStep}</p>
    {row && row.gates.length > 0 && <p className="vendor-gate-count">{row.gates.length} backend setup {row.gates.length === 1 ? "gate remains" : "gates remain"}.</p>}
    <details className="vendor-setup"><summary>Setup checklist for {title}</summary>
      {row && row.gates.length > 0 && <ul className="vendor-pending-gates" aria-label={`${title} backend setup gates`}>
        {row.gates.map((gate, index) => <li key={index}><Icon name="Pause" size={16} /><span>{Object.hasOwn(gateLabels, gate) ? gateLabels[gate] : "Additional administrator setup check required"}</span></li>)}
      </ul>}
      <ol>
        <li><strong>Official app setup.</strong> {vendor === "tapo" ? "Finish DL110 setup in the Tapo app; keep fingerprint, PIN and account details there."
          : "Finish camera setup and motion notifications in the Wansview app. ANIMA does not need video, recordings or snapshots."} App setup is not verified by this panel.</li>
        <li><strong>{vendor === "tapo" ? "Verified source setup." : "Private relay setup."}</strong> {vendor === "tapo"
          ? "The administrator verifies an actual supported HA lock source, its canonical household mapping and a genuine source sample. A compatible product name alone is not proof of support."
          : "The administrator configures a vendor-only, minimized notification relay on this PC."} Do not paste account credentials or notification contents into the dashboard.</li>
        <li><strong>Observe, then refresh.</strong> After approved setup, compare the next genuine app notification with the receipt shown here. Refresh reads status only; it never generates an event or changes a device.</li>
      </ol>
      <p>No supported browser enable or account-link action is available here. Configuration and intake enablement remain administrator-managed.</p>
    </details>
    <details className="vendor-evidence"><summary>Source &amp; time quality</summary>
      <p>This is vendor-supplied information, not a verified physical measurement. Receipt time is when ANIMA received it, not when an unlock or motion physically happened. Source event time is not supplied by this status endpoint.</p>
      <p>{vendor === "tapo" ? "A notification does not establish who unlocked the door. An HA state-cache update is not a complete stream of unlock operations. Fingerprint/profile attribution and physical lock state are not verified here."
        : "No camera image, person identity, current motion state or complete motion history is inferred."} Ready configuration or one receipt does not prove continuing delivery, SENTRY processing, speech playback or human receipt.</p>
    </details>
  </article>;
}

/** Mount inside Integrations. This component owns only its read-only status fetch. */
export function VendorConnectionsPanel({ onAuthFailure }: VendorConnectionsPanelProps) {
  const [status, setStatus] = useState<VendorConnectionsStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);
  const mounted = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const inFlight = useRef(false);
  const authFailure = useRef(onAuthFailure); authFailure.current = onAuthFailure;

  async function refresh() {
    if (!mounted.current || inFlight.current) return;
    inFlight.current = true;
    const request = new AbortController(); controller.current = request;
    const timeout = window.setTimeout(() => request.abort(), 10_000);
    setLoading(true); setError("");
    try {
      const response = await fetch(endpoint, { method: "GET", credentials: "same-origin", cache: "no-store",
        signal: request.signal, headers: { Accept: "application/json" } });
      if (!mounted.current || controller.current !== request) return;
      if (response.status === 401) {
        setStatus(null); setCheckedAt(null); setError("Your session has expired."); authFailure.current(); return;
      }
      if (!response.ok) throw new Error(response.status === 404 ? "NOT_INSTALLED" : response.status === 403 ? "FORBIDDEN" : "UNAVAILABLE");
      const value = parseStatus(await response.json());
      if (mounted.current && controller.current === request && !request.signal.aborted) { setStatus(value); setCheckedAt(new Date()); }
    } catch (reason) {
      if (!mounted.current || controller.current !== request) return;
      setStatus(null); setCheckedAt(null);
      setError(reason instanceof Error && reason.message === "NOT_INSTALLED" ? "Notification setup status is not available in this build. Ask the administrator to finish the integration, then refresh."
        : reason instanceof Error && reason.message === "FORBIDDEN" ? "Notification setup status is not available to this account."
        : "Notification status could not be verified. Earlier status has been cleared; try Refresh status.");
    } finally {
      window.clearTimeout(timeout);
      if (controller.current === request) { inFlight.current = false; if (mounted.current) setLoading(false); }
    }
  }
  useEffect(() => {
    mounted.current = true; void refresh();
    return () => { mounted.current = false; controller.current?.abort(); controller.current = null; inFlight.current = false; };
  }, []);

  return <section className="vendor-connections" aria-labelledby="vendor-connections-heading">
    <header className="vendor-panel-heading"><div><h2 id="vendor-connections-heading"><Icon name="Notifications" /> Vendor app notifications</h2>
      <p>Notification intake only · no lock controls or camera feeds</p></div>
      <button type="button" onClick={() => void refresh()} disabled={loading}><Icon name="Refresh" />{loading ? "Checking status…" : "Refresh status"}</button>
    </header>
    {error && <p className="notice error" role="alert">{error}</p>}
    <p className="vendor-check-time" role="status">{loading ? "Checking notification setup status."
      : checkedAt ? `Status checked ${checkedAt.toLocaleTimeString()}. This is not an event timestamp.` : "No verified setup status loaded."}</p>
    <div className="vendor-grid">{names.map(vendor => <VendorCard key={vendor} vendor={vendor}
      row={status?.vendors.find(item => item.vendor === vendor)} globalEnabled={status?.enabled ?? false} loading={loading} />)}</div>
  </section>;
}
