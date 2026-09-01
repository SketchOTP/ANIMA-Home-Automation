import { StrictMode, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Status = "CURRENT" | "STALE" | "UNKNOWN" | "UNAVAILABLE" | "CONFLICTING";
type Bootstrap = { identity: { display_name: string; assurance: string }; household: { name: string }; theme: { accent: string }; csrf_token: string };
type Home = { household: { name: string; status: Status; summary: string }; security: { status: Status; label: string }; presence: { people: { name: string; state: string }[] }; weather: { status: Status; summary: string }; calendar: { title: string; start_at: string }[]; tasks: { title: string; status: string }[]; activity: { summary: string; status: Status }[]; voice: { status: Status; label: string } };

const api = async <T,>(path: string, options?: RequestInit): Promise<T> => {
  const response = await fetch(path, { ...options, credentials: "same-origin", headers: { Accept: "application/json", ...(options?.headers ?? {}) } });
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail ?? "ANIMA could not complete that request");
  return response.json() as Promise<T>;
};

function StatusPill({ status }: { status: Status | string }) {
  return <span className={`status status-${status.toLowerCase().replaceAll("/", "-")}`}>{status}</span>;
}

function Card({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  return <section className={`card ${className}`}><div className="card-heading"><h2>{title}</h2></div>{children}</section>;
}

function App() {
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null);
  const [home, setHome] = useState<Home | null>(null);
  const [tab, setTab] = useState("Home");
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState("");
  const [error, setError] = useState("");

  const refresh = async () => {
    try { setError(""); const [b, h] = await Promise.all([api<Bootstrap>("/api/v1/bootstrap"), api<Home>("/api/v1/home")]); setBootstrap(b); setHome(h); }
    catch (err) { setError(err instanceof Error ? err.message : "Anima is unavailable"); }
  };
  useEffect(() => { void refresh(); }, []);
  useEffect(() => { if (!bootstrap) return; const events = new EventSource("/api/v1/events"); const invalidate = () => void refresh(); ["home.invalidated", "tasks.changed", "calendar.changed", "activity.changed", "conversation.completed", "capabilities.changed", "refresh.required"].forEach((name) => events.addEventListener(name, invalidate)); return () => events.close(); }, [bootstrap]);

  const send = async () => { if (!message.trim() || !bootstrap) return; try { const result = await api<{ response: string }>("/api/v1/conversation", { method: "POST", body: JSON.stringify({ text: message.trim() }), headers: { "Content-Type": "application/json", "X-Anima-CSRF": bootstrap.csrf_token, Origin: window.location.origin } }); setReply(result.response); setMessage(""); } catch (err) { setError(err instanceof Error ? err.message : "Anima could not respond"); } };
  const greeting = useMemo(() => bootstrap ? `Good evening, ${bootstrap.identity.display_name}.` : "Connecting to Anima…", [bootstrap]);

  if (!bootstrap || !home) return <main className="shell centered"><div className="brand-mark">A</div><h1>Anima</h1><p>{error || "Connecting to your home…"}</p>{error && <button onClick={() => void refresh()}>Try again</button>}</main>;
  return <div className="app-shell">
    <aside className="sidebar"><div className="brand"><div className="brand-mark">A</div><div><strong>Anima</strong><small>home intelligence</small></div></div><nav aria-label="Primary navigation">{["Home", "Anima", "Tasks & Calendar", "Activity", "Capabilities", "Settings"].map((item) => <button key={item} className={tab === item ? "nav-item active" : "nav-item"} onClick={() => setTab(item)}>{item}</button>)}</nav><div className="sidebar-footer"><StatusPill status="online" /><span>Local interface</span></div></aside>
    <main className="content"><header className="topbar"><div><p className="eyebrow">{bootstrap.household.name}</p><h1>{tab === "Home" ? greeting : tab}</h1></div><button className="avatar" aria-label="Current household member">H</button></header>
      {error && <div className="notice error" role="alert">{error}</div>}
      {tab === "Home" && <div className="dashboard"><Card title="At a glance" className="hero"><p className="hero-copy">{home.household.summary}</p><div className="metric-row"><div><span>Presence</span><strong>{home.presence.people[0]?.state ?? "unknown"}</strong></div><div><span>Security</span><strong><StatusPill status={home.security.status} /></strong></div><div><span>Weather</span><strong><StatusPill status={home.weather.status} /></strong></div></div></Card><Card title="People at home"><ul className="clean-list">{home.presence.people.map((person) => <li key={person.name}><span className="person-dot" />{person.name}<StatusPill status={person.state} /></li>)}</ul></Card><Card title="Weather"><p className="muted">{home.weather.summary}</p></Card><Card title="Coming up"><ul className="clean-list">{home.calendar.map((event) => <li key={event.title}><span>{event.title}</span><time>{new Date(event.start_at).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" })}</time></li>)}</ul></Card><Card title="Things to do"><ul className="clean-list">{home.tasks.map((task) => <li key={task.title}><span>{task.title}</span><StatusPill status={task.status} /></li>)}</ul></Card><Card title="Anima"><p className="muted">{reply || "I’m here when you need a hand."}</p></Card><Card title="Voice"><p className="muted">{home.voice.label}</p></Card></div>}
      {tab === "Anima" && <Card title="Talk with Anima" className="conversation"><p className="muted">Ask about your home, plan a reminder, or request help. Responses stay within the local ANIMA boundary.</p><div className="composer"><label htmlFor="message">Message Anima</label><textarea id="message" value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void send(); } }} placeholder="What would you like to know?" /><button onClick={() => void send()}>Send</button></div>{reply && <div className="reply" aria-live="polite"><strong>Anima</strong><p>{reply}</p></div>}</Card>}
      {tab === "Tasks & Calendar" && <div className="dashboard"><Card title="Tasks"><ul className="clean-list">{home.tasks.map((task) => <li key={task.title}><span>{task.title}</span><StatusPill status={task.status} /></li>)}</ul></Card><Card title="Calendar"><ul className="clean-list">{home.calendar.map((event) => <li key={event.title}><span>{event.title}</span><time>{new Date(event.start_at).toLocaleString()}</time></li>)}</ul></Card></div>}
      {tab === "Activity" && <Card title="Recent activity"><ul className="clean-list">{home.activity.map((item) => <li key={item.summary}><span>{item.summary}</span><StatusPill status={item.status} /></li>)}</ul></Card>}
      {tab === "Capabilities" && <Capabilities />}
      {tab === "Settings" && <Card title="Household interface"><p className="muted">One shared Anima interface. Display, theme, density, visibility, and accessibility are bounded household configuration.</p><div className="settings-grid"><span>Appearance</span><strong>Night</strong><span>Accent</span><strong>{bootstrap.theme.accent}</strong><span>Voice</span><strong>Unavailable until a later phase</strong></div></Card>}
    </main></div>;
}

function Capabilities() { const [items, setItems] = useState<{ label: string; state: string; detail?: string }[]>([]); useEffect(() => { void api<{ items: typeof items }>("/api/v1/capabilities").then((result) => setItems(result.items)); }, []); return <Card title="Capabilities"><ul className="clean-list">{items.map((item) => <li key={item.label}><span>{item.label}</span><StatusPill status={item.state} /></li>)}</ul></Card>; }

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
