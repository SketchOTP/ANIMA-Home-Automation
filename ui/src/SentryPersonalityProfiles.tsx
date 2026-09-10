import { useEffect, useState } from "react";
import type { FormEvent } from "react";

export type SentryPersonalityProfile = {
  profile_id: string;
  name: string;
  profile_text: string;
  version: string;
  active: boolean;
  updated_at: string;
};

export type SentryPersonalityProfilesPayload = {
  items: SentryPersonalityProfile[];
  active_profile_id: string | null;
  fallback_active: boolean;
  fallback_name: string;
  boundary: string;
};

type MutationResult = {
  status: string;
  operation: string;
  profiles: SentryPersonalityProfilesPayload;
};

type Props = {
  value: SentryPersonalityProfilesPayload | null;
  csrfToken: string;
  onChanged: (value: SentryPersonalityProfilesPayload) => void;
  onOutcome: (value: { status: string; operation: string; detail: string }) => void;
  onError: (value: string) => void;
};

async function mutateProfile(
  operation: string,
  payload: Record<string, unknown>,
  csrfToken: string,
): Promise<MutationResult> {
  const response = await fetch(`/api/v1/sentry/personality-profiles/${operation}`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-Anima-CSRF": csrfToken,
    },
    body: JSON.stringify({ payload }),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? "SENTRY personality profile could not be saved");
  }
  return response.json() as Promise<MutationResult>;
}

export function SentryPersonalityProfiles({
  value,
  csrfToken,
  onChanged,
  onOutcome,
  onError,
}: Props) {
  const [editing, setEditing] = useState<SentryPersonalityProfile | null>(null);
  const [name, setName] = useState("");
  const [profileText, setProfileText] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  useEffect(() => {
    if (!editing) return;
    if (!value?.items.some((item) => item.profile_id === editing.profile_id)) {
      setEditing(null);
      setName("");
      setProfileText("");
    }
  }, [editing, value]);

  const reset = () => {
    setEditing(null);
    setName("");
    setProfileText("");
    setConfirmDelete(null);
  };

  const run = async (operation: string, payload: Record<string, unknown>, detail: string) => {
    setBusy(true);
    setConfirmDelete(null);
    try {
      const result = await mutateProfile(operation, payload, csrfToken);
      onChanged(result.profiles);
      onOutcome({ status: result.status, operation: result.operation, detail });
      onError("");
      return true;
    } catch (error) {
      onError(error instanceof Error ? error.message : "SENTRY personality could not be changed");
      return false;
    } finally {
      setBusy(false);
    }
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    const operation = editing ? "update" : "create";
    const payload: Record<string, unknown> = { name, profile_text: profileText };
    if (editing) {
      payload.profile_id = editing.profile_id;
      payload.expected_version = editing.version;
    }
    const saved = await run(
      operation,
      payload,
      editing ? `Updated personality profile ${name}` : `Saved personality profile ${name}`,
    );
    if (saved) reset();
  };

  const beginEdit = (profile: SentryPersonalityProfile) => {
    setEditing(profile);
    setName(profile.name);
    setProfileText(profile.profile_text);
    setConfirmDelete(null);
  };

  return (
    <section className="card personality-manager" aria-labelledby="sentry-personality-heading">
      <div className="card-heading">
        <h2 id="sentry-personality-heading">SENTRY personality</h2>
      </div>
      <p className="muted">
        Write SENTRY&apos;s voice and conversational character in your own words. Save several
        profiles and activate one at a time. New profiles are saved inactive until you explicitly
        activate them. Choose Built-in SENTRY to return to the default style without deleting profiles.
      </p>
      <p className="notice warning personality-boundary">
        {value?.boundary ?? "Personality changes presentation only; ANIMA safety and authority always win."}
      </p>

      <form className="stack personality-editor" onSubmit={(event) => void save(event)}>
        <label>
          Profile name
          <input
            required
            maxLength={80}
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="For example: Warm household host"
          />
        </label>
        <label>
          Personality profile
          <textarea
            required
            maxLength={4000}
            rows={9}
            value={profileText}
            onChange={(event) => setProfileText(event.target.value)}
            placeholder="Describe SENTRY's tone, manner, humor, formality, vocabulary, and conversational style."
          />
        </label>
        <div className="editor-meta">
          <span>{profileText.length} / 4000 characters</span>
          <span>Plain text · presentation guidance only</span>
        </div>
        <div className="button-row">
          <button type="submit" disabled={busy || !name.trim() || !profileText.trim()}>
            {editing ? "Save changes" : "Save new profile"}
          </button>
          {editing && <button type="button" disabled={busy} onClick={reset}>Cancel edit</button>}
        </div>
      </form>

      <div className="saved-personalities" aria-live="polite">
        <h3>Saved profiles</h3>
        <div className="button-row personality-default-choice">
          <button
            type="button"
            disabled={busy || value?.fallback_active === true}
            onClick={() => void run(
              "activate_default",
              {},
              "Activated built-in SENTRY presentation",
            )}
          >
            Built-in SENTRY
          </button>
          {value?.fallback_active && <span className="status status-active">DEFAULT ACTIVE</span>}
        </div>
        {value?.items.length ? (
          <ul className="clean-list list-spaced">
            {value.items.map((profile) => (
              <li className="personality-row" key={profile.profile_id}>
                <div className="personality-copy">
                  <div className="personality-title">
                    <strong>{profile.name}</strong>
                    {profile.active && <span className="status status-active">ACTIVE</span>}
                  </div>
                  <p>{profile.profile_text}</p>
                  <small className="muted">
                    Updated {new Date(profile.updated_at).toLocaleString()}
                  </small>
                </div>
                <div className="button-row">
                  <button type="button" disabled={busy} onClick={() => beginEdit(profile)}>Edit</button>
                  <button
                    type="button"
                    disabled={busy || profile.active}
                    onClick={() => void run(
                      "activate",
                      { profile_id: profile.profile_id, expected_version: profile.version },
                      `Activated personality profile ${profile.name}`,
                    )}
                  >
                    {profile.active ? "Active" : "Activate"}
                  </button>
                  {confirmDelete === profile.profile_id ? (
                    <>
                      <button
                        type="button"
                        className="danger-button"
                        disabled={busy}
                        onClick={() => void run(
                          "delete",
                          { profile_id: profile.profile_id, expected_version: profile.version },
                          `Deleted personality profile ${profile.name}`,
                        )}
                      >
                        Confirm delete
                      </button>
                      <button type="button" disabled={busy} onClick={() => setConfirmDelete(null)}>
                        Keep
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => setConfirmDelete(profile.profile_id)}
                    >
                      Delete
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="empty-state">
            No saved profiles. SENTRY is using {value?.fallback_name ?? "its built-in personality"}.
          </p>
        )}
      </div>
    </section>
  );
}
