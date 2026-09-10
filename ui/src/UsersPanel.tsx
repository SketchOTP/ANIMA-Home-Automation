import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "./visuals";
import "./UsersPanel.css";

type AccessLevel = "UNRESTRICTED" | "LIMITED";
type PersonRole = "owner" | "member" | "guest";
type OnboardingState = "NOT_STARTED" | "PENDING_CAMERA_PROFILE" | "ACTIVE" | "REVOKED";
type User = {
  person_id: string;
  name: string;
  role: PersonRole;
  access_level: AccessLevel;
  sentry_profile_id: string | null;
  sentry_profile_sample_count: number | null;
  sentry_onboarding_state: OnboardingState;
  wifi_macs: string[];
};
type UserPage = { items: User[] };
type Outcome = { status: string; result?: unknown; reason?: string };
export type UsersPanelProps = {
  mutate: (path: string, payload?: Record<string, unknown>) => Promise<Outcome | null>;
  onAuthFailure: () => void;
};
type Draft = { name: string; role: PersonRole; access_level: AccessLevel; wifi_macs: string };
type FaceSample = {
  sample_id: string;
  pose: string | null;
  quality: Record<string, unknown>;
  preview_jpeg_base64: string | null;
};
type Enrollment = {
  session_id: string;
  person_id: string;
  display_name: string;
  accepted_samples: number;
  target_samples: number;
  ready_to_save: boolean;
  accepted_poses: Record<string, number>;
  samples: FaceSample[];
};

// Finish with the easiest straight-on capture. Side profiles are collected
// earlier so the final response is not coupled to the hardest detector angle.
const POSES = ["straight", "left", "right", "up", "down", "left", "right", "straight"] as const;
type FacePose = (typeof POSES)[number];
const POSE_TARGETS: Record<FacePose, number> = {
  straight: 2,
  left: 2,
  right: 2,
  up: 1,
  down: 1,
};
const poseGuidance: Record<string, string> = {
  straight: "Look directly at the camera.",
  left: "Turn your head slightly to your left.",
  right: "Turn your head slightly to your right.",
  up: "Tilt your face slightly upward.",
  down: "Tilt your face slightly downward.",
};
const blank = (): Draft => ({ name: "", role: "member", access_level: "LIMITED", wifi_macs: "" });
const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const isMac = (value: string) => /^[0-9a-f]{2}(:[0-9a-f]{2}){5}$/i.test(value);

const parsePage = (value: unknown): UserPage => {
  if (!object(value) || !Array.isArray(value.items)) throw new Error("INVALID_USERS_RESPONSE");
  const items = value.items.map((item): User => {
    if (!object(item) || typeof item.person_id !== "string" || typeof item.name !== "string" || !["owner", "member", "guest"].includes(String(item.role)) || !["UNRESTRICTED", "LIMITED"].includes(String(item.access_level)) || !["NOT_STARTED", "PENDING_CAMERA_PROFILE", "ACTIVE", "REVOKED"].includes(String(item.sentry_onboarding_state)) || !Array.isArray(item.wifi_macs) || !item.wifi_macs.every(mac => typeof mac === "string" && isMac(mac))) throw new Error("INVALID_USERS_RESPONSE");
    const count = item.sentry_profile_sample_count;
    if (count !== null && count !== undefined && (!Number.isInteger(count) || Number(count) < 1 || Number(count) > 16)) throw new Error("INVALID_USERS_RESPONSE");
    return {
      person_id: item.person_id,
      name: item.name,
      role: item.role as PersonRole,
      access_level: item.access_level as AccessLevel,
      sentry_profile_id: typeof item.sentry_profile_id === "string" ? item.sentry_profile_id : null,
      sentry_profile_sample_count: typeof count === "number" ? count : null,
      sentry_onboarding_state: item.sentry_onboarding_state as OnboardingState,
      wifi_macs: item.wifi_macs,
    };
  });
  if (new Set(items.map(item => item.person_id)).size !== items.length) throw new Error("INVALID_USERS_RESPONSE");
  return { items };
};

function enrollmentFrom(outcome: Outcome | null): Enrollment | null {
  if (!outcome || outcome.status !== "SUCCEEDED" || !object(outcome.result)) return null;
  const value = outcome.result;
  if (typeof value.session_id !== "string" || typeof value.person_id !== "string" || typeof value.display_name !== "string" || typeof value.accepted_samples !== "number" || typeof value.target_samples !== "number" || typeof value.ready_to_save !== "boolean" || !object(value.accepted_poses) || !Array.isArray(value.samples)) return null;
  const samples = value.samples.filter(object).map((sample): FaceSample => ({
    sample_id: String(sample.sample_id ?? ""),
    pose: typeof sample.pose === "string" ? sample.pose : null,
    quality: object(sample.quality) ? sample.quality : {},
    preview_jpeg_base64: typeof sample.preview_jpeg_base64 === "string" ? sample.preview_jpeg_base64 : null,
  })).filter(sample => sample.sample_id);
  return { session_id: value.session_id, person_id: value.person_id, display_name: value.display_name, accepted_samples: value.accepted_samples, target_samples: value.target_samples, ready_to_save: value.ready_to_save, accepted_poses: value.accepted_poses as Record<string, number>, samples };
}

function onboardingLabel(user: User) {
  if (user.sentry_onboarding_state === "ACTIVE") return `Face profile active${user.sentry_profile_sample_count ? ` · ${user.sentry_profile_sample_count} captures` : ""}`;
  if (user.sentry_onboarding_state === "PENDING_CAMERA_PROFILE") return "Face profile ready to register";
  if (user.sentry_onboarding_state === "REVOKED") return "Face profile removed";
  return "No face profile";
}

function nextRequiredPose(enrollment: Enrollment): FacePose {
  const remaining = { ...POSE_TARGETS };
  for (const [pose, count] of Object.entries(enrollment.accepted_poses)) {
    if (pose in remaining) remaining[pose as FacePose] -= Number(count) || 0;
  }
  return POSES.find((pose) => remaining[pose] > 0) ?? "straight";
}

export function UsersPanel({ mutate, onAuthFailure }: UsersPanelProps) {
  const [page, setPage] = useState<UserPage | null>(null);
  const [draft, setDraft] = useState<Draft>(blank);
  const [editing, setEditing] = useState<User | null>(null);
  const [enrolling, setEnrolling] = useState<User | null>(null);
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [faceBusy, setFaceBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const heading = useRef<HTMLHeadingElement>(null);
  const controller = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const authFailure = useRef(onAuthFailure);
  authFailure.current = onAuthFailure;

  const reload = useCallback(async () => {
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    const current = ++generation.current;
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/v1/users", { credentials: "same-origin", cache: "no-store", signal: abort.signal, headers: { Accept: "application/json" } });
      if (current !== generation.current) return;
      if (response.status === 401) { authFailure.current(); return; }
      if (!response.ok) throw new Error("USERS_UNAVAILABLE");
      setPage(parsePage(await response.json()));
    } catch (reason) {
      if (current === generation.current && !abort.signal.aborted) setError(reason instanceof Error && reason.message === "INVALID_USERS_RESPONSE" ? "ANIMA returned an invalid household-user response." : "Household users could not be loaded. Retry when Core is connected.");
    } finally {
      if (current === generation.current) setLoading(false);
    }
  }, []);
  useEffect(() => { void reload(); return () => { generation.current++; controller.current?.abort(); }; }, [reload]);

  const reset = () => { setDraft(blank()); setEditing(null); };
  const edit = (user: User) => {
    setEditing(user);
    setDraft({ name: user.name, role: user.role, access_level: user.access_level, wifi_macs: user.wifi_macs.join("\n") });
    setNotice("");
    heading.current?.focus();
  };
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy || !draft.name.trim()) return;
    const macs = draft.wifi_macs.split(/[,;\n]+/).map(value => value.trim().toLowerCase().replaceAll("-", ":")).filter(Boolean);
    if (macs.some(mac => !isMac(mac))) { setError("Each Wi-Fi address must be a complete MAC address."); return; }
    if (new Set(macs).size !== macs.length || macs.length > 8) { setError("Use up to eight unique Wi-Fi addresses."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await mutate(`/api/v1/users/${editing ? "update" : "create"}`, { ...(editing ? { person_id: editing.person_id } : {}), name: draft.name, role: draft.role, access_level: draft.access_level, wifi_macs: macs });
      if (result?.status === "SUCCEEDED") { reset(); setNotice(editing ? "Household user, SENTRY access, and Wi-Fi identity hints saved." : "Household user added. You can register their face profile below."); await reload(); }
    } finally { setBusy(false); }
  };
  const startFace = async (user: User) => {
    setFaceBusy(true); setError(""); setNotice("");
    try {
      const result = await mutate("/api/v1/users/face-start", { person_id: user.person_id });
      const session = enrollmentFrom(result);
      if (!session) { setError(result?.reason || "SENTRY could not start face enrollment."); return; }
      setEnrolling(user); setEnrollment(session);
    } finally { setFaceBusy(false); }
  };
  const captureFace = async (pose?: FacePose) => {
    if (!enrolling || !enrollment) return;
    const requestedPose = pose ?? nextRequiredPose(enrollment);
    if (Number(enrollment.accepted_poses[requestedPose] ?? 0) >= POSE_TARGETS[requestedPose]) return;
    setFaceBusy(true); setError("");
    try {
      const result = await mutate("/api/v1/users/face-capture", { person_id: enrolling.person_id, session_id: enrollment.session_id, pose: requestedPose });
      const session = enrollmentFrom(result);
      if (!session) { setError(result?.reason || "No clear face was captured. Adjust position or lighting and try again."); return; }
      setEnrollment(session);
      if (session.accepted_samples === enrollment.accepted_samples) {
        const detail = object(result?.result) && typeof result.result.reason === "string" ? result.result.reason : null;
        setError(detail || "No clear face was captured. Adjust position or lighting and try again.");
      }
    } finally { setFaceBusy(false); }
  };
  const removeSample = async (sampleId: string) => {
    if (!enrolling || !enrollment) return;
    setFaceBusy(true); setError("");
    try {
      const result = await mutate("/api/v1/users/face-remove-sample", { person_id: enrolling.person_id, session_id: enrollment.session_id, sample_id: sampleId });
      const session = enrollmentFrom(result);
      if (session) setEnrollment(session); else setError(result?.reason || "That capture could not be removed.");
    } finally { setFaceBusy(false); }
  };
  const cancelFace = async () => {
    if (!enrolling || !enrollment) return;
    setFaceBusy(true);
    try {
      await mutate("/api/v1/users/face-cancel", { person_id: enrolling.person_id, session_id: enrollment.session_id });
      setEnrolling(null); setEnrollment(null);
    } finally { setFaceBusy(false); }
  };
  const commitFace = async () => {
    if (!enrolling || !enrollment) return;
    setFaceBusy(true); setError("");
    try {
      const result = await mutate("/api/v1/users/face-commit", { person_id: enrolling.person_id, session_id: enrollment.session_id });
      if (result?.status === "SUCCEEDED") { setEnrolling(null); setEnrollment(null); setNotice(`Face profile saved for ${enrolling.name}.`); await reload(); }
      else setError(result?.reason || "The face profile could not be saved.");
    } finally { setFaceBusy(false); }
  };
  const deleteFace = async (user: User) => {
    if (!window.confirm(`Remove ${user.name}'s SENTRY face profile?`)) return;
    setFaceBusy(true); setError("");
    try {
      const result = await mutate("/api/v1/users/face-delete", { person_id: user.person_id });
      if (result?.status === "SUCCEEDED") { setNotice(`Face profile removed for ${user.name}.`); await reload(); }
    } finally { setFaceBusy(false); }
  };
  const nextPose = enrollment ? nextRequiredPose(enrollment) : "straight";
  const completePoses = enrollment ? ["straight", "left", "right", "up", "down"].every(pose => Number(enrollment.accepted_poses[pose] ?? 0) > 0) : false;
  const readyToSave = Boolean(enrollment && enrollment.accepted_samples >= enrollment.target_samples && completePoses);

  return <div className="dashboard users-panel">
    <section className="card">
      <div className="card-heading"><h2 ref={heading} tabIndex={-1}><Icon name="Person" />{editing ? "Edit household user" : "Add household user"}</h2><button type="button" disabled={loading || busy || faceBusy} onClick={() => void reload()}><Icon name="Refresh" />Refresh</button></div>
      <p className="muted">Manage each person's household role, SENTRY access, Wi-Fi presence hints, and private local face profile. Wi-Fi presence supports context but never authenticates someone.</p>
      {error && <p className="notice error" role="alert">{error}</p>}{notice && <p className="notice success" role="status">{notice}</p>}
      <form className="stack" onSubmit={event => void save(event)}><fieldset disabled={busy || loading}><legend>{editing ? "User details" : "New household user"}</legend><label>Name<input required maxLength={120} value={draft.name} onChange={event => setDraft(current => ({ ...current, name: event.target.value }))} placeholder="Household member name" /></label><div className="settings-form"><label>Household role<select value={draft.role} onChange={event => setDraft(current => ({ ...current, role: event.target.value as PersonRole }))}><option value="member">Member</option><option value="guest">Guest</option>{editing && <option value="owner">Owner</option>}</select></label><label>SENTRY access<select value={draft.access_level} onChange={event => setDraft(current => ({ ...current, access_level: event.target.value as AccessLevel }))}><option value="LIMITED">Limited</option><option value="UNRESTRICTED">Unrestricted</option></select></label></div><label>Associated Wi-Fi MAC addresses<textarea rows={3} value={draft.wifi_macs} onChange={event => setDraft(current => ({ ...current, wifi_macs: event.target.value }))} placeholder="aa:bb:cc:dd:ee:ff" aria-describedby="users-mac-help" /></label><small id="users-mac-help" className="muted">Optional. Enter one per line, or separate them with commas. Saved addresses survive restarts.</small><div className="button-row"><button type="submit" disabled={busy || !draft.name.trim()}>{busy ? "Saving…" : editing ? "Save user" : "Add user"}</button>{editing && <button type="button" onClick={reset}>Cancel</button>}</div></fieldset></form>
    </section>
    <section className="card" aria-busy={loading}>
      <div className="card-heading"><h2><Icon name="Users" />Household users</h2></div>
      {loading && <p role="status">Loading household users…</p>}{!loading && page?.items.length === 0 && <p className="empty-state">No additional household users are recorded yet.</p>}
      <ul className="clean-list user-cards">{page?.items.map(user => <li key={user.person_id}>
        <div className="user-heading"><span className="user-avatar" aria-hidden="true">{user.name.slice(0, 1).toUpperCase()}</span><span><strong>{user.name}</strong><small className="muted">{user.role} · {user.access_level === "UNRESTRICTED" ? "Unrestricted SENTRY access" : "Limited SENTRY access"}</small></span><span className={`status status-${user.access_level.toLowerCase()}`}>{user.access_level.replaceAll("_", " ")}</span></div>
        <div className="user-facts"><span><strong>Face profile</strong><small>{onboardingLabel(user)}</small></span><span><strong>Wi-Fi identity hints</strong><small>{user.wifi_macs.length ? user.wifi_macs.join(" · ") : "None associated"}</small></span></div>
        <p className="muted">{user.sentry_onboarding_state === "ACTIVE" ? "SENTRY can use this local biometric profile as recognition evidence. Improving it replaces the profile with a new reviewed capture set." : "Register a private face profile with the configured SENTRY camera."}</p>
        <div className="button-row"><button type="button" disabled={faceBusy} onClick={() => edit(user)}>Edit user</button><button type="button" disabled={faceBusy} onClick={() => void startFace(user)}>{user.sentry_onboarding_state === "ACTIVE" ? "Improve face profile" : "Register face profile"}</button>{user.sentry_onboarding_state === "ACTIVE" && <button type="button" disabled={faceBusy} onClick={() => void deleteFace(user)}>Remove face profile</button>}</div>
        {enrolling?.person_id === user.person_id && enrollment && <div className="face-enrollment" aria-busy={faceBusy}><div><h3>Face profile for {user.name}</h3><p>{poseGuidance[nextPose]} Make sure one face is clearly visible and evenly lit.</p><p className="muted">{enrollment.accepted_samples} of {enrollment.target_samples} captures accepted. Eight reviewed captures are required; you can choose another view and return to a difficult one. The final recommended picture is straight-on.</p></div><div className="button-row face-pose-controls" role="group" aria-label="Choose face view">{(["straight", "left", "right", "up", "down"] as FacePose[]).map(pose => <button type="button" key={pose} disabled={faceBusy || enrollment.accepted_samples >= enrollment.target_samples || Number(enrollment.accepted_poses[pose] ?? 0) >= POSE_TARGETS[pose]} onClick={() => void captureFace(pose)}>Capture {pose} ({Number(enrollment.accepted_poses[pose] ?? 0)}/{POSE_TARGETS[pose]})</button>)}</div><div className="face-samples">{enrollment.samples.map((sample, index) => <figure key={sample.sample_id}><div className="face-preview">{sample.preview_jpeg_base64 ? <img src={`data:image/jpeg;base64,${sample.preview_jpeg_base64}`} alt={`${user.name} capture ${index + 1}, ${sample.pose ?? "face"}`} /> : <Icon name="Person" />}</div><figcaption><strong>{sample.pose ?? `Capture ${index + 1}`}</strong><small className="muted">Sharpness {String(sample.quality.sharpness ?? "accepted")}</small>{sample.quality.pose_verified === false && <small className="muted">Pose estimate uncertain; review this picture.</small>}<button type="button" disabled={faceBusy} onClick={() => void removeSample(sample.sample_id)}>Remove this capture</button></figcaption></figure>)}</div><div className="button-row"><button type="button" disabled={faceBusy || enrollment.accepted_samples >= enrollment.target_samples} onClick={() => void captureFace()}>{faceBusy ? "Using camera…" : `Take recommended ${nextPose} picture`}</button><button type="button" disabled={faceBusy || !readyToSave} onClick={() => void commitFace()}>Save face profile</button><button type="button" disabled={faceBusy} onClick={() => void cancelFace()}>Cancel enrollment</button></div><p className="muted privacy-note">Captured pictures stay in temporary memory only. After saving, SENTRY keeps the derived face profile and capture count—not the photos. To replace a poor saved profile, choose Improve face profile.</p></div>}
      </li>)}</ul>
    </section>
  </div>;
}
