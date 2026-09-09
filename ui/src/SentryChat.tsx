import { useEffect, useRef, useState } from "react";
import { Icon } from "./visuals";

type Message = { id: string; role: "user" | "sentry"; text: string; status?: string };
type Props = { csrfToken: string; suggestion: string; onAuthFailure: () => void };
const terminal = new Set(["COMPLETED", "NO_ACTION", "FAILED", "UNKNOWN_RESULT", "RECOVERY_REQUIRED", "CANCELLED"]);

export function SentryChat({ csrfToken, suggestion, onAuthFailure }: Props) {
  const [text, setText] = useState(""); const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const abort = useRef<AbortController | null>(null); const end = useRef<HTMLDivElement>(null);
  useEffect(() => { if (suggestion) setText(suggestion); }, [suggestion]);
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest" }); }, [messages]);
  useEffect(() => () => abort.current?.abort(), []);

  const send = async (event: React.FormEvent) => {
    event.preventDefault(); const prompt = text.trim(); if (!prompt || busy) return;
    const controller = new AbortController(); abort.current = controller; setBusy(true); setError(""); setText("");
    const userId = crypto.randomUUID(); setMessages(current => [...current, { id: userId, role: "user", text: prompt }]);
    try {
      const response = await fetch("/api/v1/conversation", { method: "POST", credentials: "same-origin", signal: controller.signal,
        headers: { Accept: "application/json", "Content-Type": "application/json", "X-Anima-CSRF": csrfToken, Origin: window.location.origin }, body: JSON.stringify({ text: prompt }) });
      if (response.status === 401) { onAuthFailure(); return; }
      if (!response.ok) throw new Error((await response.json().catch(() => ({})) as { detail?: string }).detail ?? "SENTRY is unavailable.");
      const queued = await response.json() as { request_id: string; response?: string; disposition?: string };
      const sentryId = crypto.randomUUID();
      setMessages(current => [...current, { id: sentryId, role: "sentry", text: queued.response ?? "SENTRY received your request.", status: queued.disposition }]);
      for (let attempt = 0; attempt < 300; attempt += 1) {
        await new Promise(resolve => window.setTimeout(resolve, 1000));
        const resultResponse = await fetch(`/api/v1/conversation/${encodeURIComponent(queued.request_id)}`, { credentials: "same-origin", cache: "no-store", signal: controller.signal, headers: { Accept: "application/json" } });
        if (resultResponse.status === 401) { onAuthFailure(); return; }
        if (!resultResponse.ok) continue;
        const result = await resultResponse.json() as { lifecycle: string; response?: string | null; detail?: string | null; status: string; available: boolean };
        setMessages(current => current.map(message => message.id === sentryId ? { ...message, text: result.response ?? result.detail ?? "SENTRY is still working…", status: result.status } : message));
        if (result.available || terminal.has(result.lifecycle)) return;
      }
      setError("SENTRY is still working. Keep this page open to receive the live result; the durable operation remains visible in Activity.");
    } catch (reason) {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "SENTRY could not complete the request.");
    } finally { if (!controller.signal.aborted) setBusy(false); }
  };

  return <section className="sentry-chat" aria-labelledby="sentry-chat-title">
    <header className="sentry-chat-header"><span className="assistant-orb"><Icon name="Anima" size={34} /></span><div><h2 id="sentry-chat-title">SENTRY owner operations</h2><p>Tell SENTRY the result you want in ordinary language. It can inspect and change supported ANIMA devices, alerts, routines, users, tasks, calendar, scenes, automations, preferences, backups, and integrations end to end.</p></div></header>
    <div className="chat-boundary"><Icon name="Check" size={18} /><span>Your authenticated owner session supplies authority. SENTRY uses typed ANIMA operations and reports policy, confirmation, stronger-auth, and physical verification results honestly; credentials and raw host access never enter the conversation.</span></div>
    <div className="chat-transcript" aria-live="polite">{messages.length ? messages.map(message => <article className={`chat-message chat-${message.role}`} key={message.id}><strong>{message.role === "user" ? "You" : "SENTRY"}</strong><p>{message.text}</p>{message.status && <small>{message.status.replaceAll("_", " ")}</small>}</article>) : <div className="chat-empty"><Icon name="Anima" size={28} /><strong>What would you like to change?</strong><p>Try “Add a motion alert from midnight to 5 AM,” “create a scene,” or “help me set up this new device.”</p></div>}<div ref={end} /></div>
    {error && <p className="notice error" role="alert">{error}</p>}
    <form className="chat-composer" onSubmit={event => void send(event)}><label htmlFor="sentry-message">Tell SENTRY what to do</label><textarea id="sentry-message" maxLength={4000} value={text} disabled={busy} onChange={event => setText(event.target.value)} placeholder="For example: Always announce when the front-door lock is unlocked." /><div><small>Live conversation text is cleared from this browser on reload. Completed changes persist in ANIMA and appear in the relevant page and Activity.</small><button className="primary" type="submit" disabled={busy || !text.trim()}><Icon name="ArrowRight" />{busy ? "SENTRY is working…" : "Send to SENTRY"}</button></div></form>
  </section>;
}
