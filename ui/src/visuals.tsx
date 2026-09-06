import type { CSSProperties, ReactNode, SVGProps } from "react";

// Small, local SVG vocabulary: no remote assets, icon fonts, or runtime fetching.
const paths = {
  home: "m3 10 9-7 9 7M5 9v12h5v-7h4v7h5V9",
  devices: "M8 3h8v18H8zM11 17h2M10 6h4",
  spaces: "M3 3h8v8H3zM15 3h6v8h-6zM3 15h8v6H3zM15 15h6v6h-6z",
  scenes: "m12 3 9 5-9 5-9-5zM3 12l9 5 9-5M3 16l9 5 9-5",
  automations: "m13 2-9 12h7l-1 8 10-12h-7z",
  alerts: "m12 3 10 18H2zM12 9v5M12 17v.1",
  notifications: "M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4",
  anima: "M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1M12 7l5 5-5 5-5-5z",
  message: "M21 4H3v14h5l4 4v-4h9zM7 9h10M7 13h6",
  calendar: "M4 5h16v16H4zM8 3v4M16 3v4M4 10h16M8 14h2M14 14h2M8 18h2",
  activity: "M2 12h5l3-8 4 16 3-8h5",
  capabilities: "m12 3 8 4v6c0 4-8 8-8 8s-8-4-8-8V7zM8 12l3 3 5-6",
  integrations: "M8 3v5M16 3v5M6 8h12v3a6 6 0 0 1-12 0zM12 17v5",
  backups: "M4 3h14l3 3v15H3V3zM7 3v6h10V3M7 21v-8h10v8",
  preferences: "M4 7h6M14 7h6M4 17h10M18 17h2M10 4v6M14 14v6",
  settings: "M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8",
  user: "M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8M4 21v-2a8 8 0 0 1 16 0v2",
  people: "M9 4a3 3 0 1 0 0 6 3 3 0 0 0 0-6M2 20v-2a7 7 0 0 1 14 0v2M17 4a3 3 0 0 1 0 6M19 13a5 5 0 0 1 3 5v2",
  sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M5 19l1.5-1.5M17.5 6.5 19 5",
  moon: "M21 13A9 9 0 0 1 11 3 9 9 0 1 0 21 13z",
  cloud: "M7 18a5 5 0 1 1 1-10 7 7 0 0 1 13 3 4 4 0 0 1-1 7z",
  temperature: "M9 14V5a3 3 0 0 1 6 0v9a5 5 0 1 1-6 0M12 8v10M18 6h3M18 10h2",
  humidity: "M12 3s-7 8-7 12a7 7 0 0 0 14 0c0-4-7-12-7-12zM9 16a3 3 0 0 0 3 3",
  light: "M9 18h6M10 21h4M9 15a7 7 0 1 1 6 0v3H9z",
  power: "M12 2v10M6 5a9 9 0 1 0 12 0",
  lock: "M5 10h14v11H5zM8 10V6a4 4 0 0 1 8 0v4M12 14v3",
  unlock: "M5 10h14v11H5zM8 10V6a4 4 0 0 1 8 0M12 14v3",
  wifi: "M2 8a16 16 0 0 1 20 0M5 12a11 11 0 0 1 14 0M8 16a6 6 0 0 1 8 0M12 20v.1",
  offline: "M2 2l20 20M2 8a16 16 0 0 1 3-2M10 5a16 16 0 0 1 12 3M5 12a11 11 0 0 1 4-2M15 10a11 11 0 0 1 4 2M8 16a6 6 0 0 1 8 0M12 20v.1",
  chart: "M3 3v18h18M7 17v-5M12 17V7M17 17v-8",
  check: "m5 12 4 4L19 6",
  plus: "M12 5v14M5 12h14",
  close: "m6 6 12 12M6 18 18 6",
  arrow: "M4 12h16m-6-6 6 6-6 6",
  chevron: "m9 5 7 7-7 7",
  up: "m5 15 7-7 7 7",
  down: "m5 9 7 7 7-7",
  refresh: "M20 8a9 9 0 0 0-15-3L2 8M2 3v5h5M4 16a9 9 0 0 0 15 3l3-3M22 21v-5h-5",
  search: "M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14m5 12 6 6",
  send: "m22 2-7 20-4-9-9-4zM11 13 22 2",
  edit: "m14 5 5 5M4 15 16 3l5 5L9 20l-6 1z",
  trash: "M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7",
  clock: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18M12 7v5l4 2",
  play: "m7 3 14 9-14 9z",
  pause: "M7 4v16M17 4v16",
  info: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18M12 11v6M12 7v.1",
  heart: "M12 21 3 12a5.5 5.5 0 0 1 9-7 5.5 5.5 0 0 1 9 7z",
  menu: "M3 6h18M3 12h18M3 18h18",
  monitor: "M3 3h18v14H3zM8 21h8M12 17v4",
  connection: "m9 15 6-6M8 16l-2 2a4 4 0 0 1-5-6l4-4a4 4 0 0 1 6 0M16 8l2-2a4 4 0 0 1 5 6l-4 4a4 4 0 0 1-6 0",
} as const;

export type IconName = keyof typeof paths;
const aliases: Record<string, IconName> = {
  "tasks & calendar": "calendar", tasks: "calendar", task: "calendar", agenda: "calendar",
  rooms: "spaces", room: "spaces", grid: "spaces", device: "devices", smartphone: "devices",
  scene: "scenes", layers: "scenes", automation: "automations", bolt: "automations", energy: "automations",
  alert: "alerts", warning: "alerts", bell: "notifications", notification: "notifications",
  assistant: "anima", sentry: "anima", sparkles: "anima", chat: "message", conversation: "message",
  shield: "capabilities", security: "capabilities", health: "activity", pulse: "activity",
  plug: "integrations", integration: "integrations", backup: "backups", database: "backups", save: "backups",
  sliders: "preferences", weather: "cloud", person: "user", presence: "people", users: "people",
  bulb: "light", lightbulb: "light", lights: "light", thermometer: "temperature",
  add: "plus", remove: "trash", delete: "trash", cancel: "close", x: "close",
  connect: "connection", link: "connection", login: "arrow", logout: "arrow", signin: "arrow",
  "arrow-right": "arrow", "chevron-right": "chevron", "chevron-up": "up", "chevron-down": "down",
  on: "power", off: "power", retry: "refresh", reconnect: "refresh", done: "check", success: "check",
  night: "moon", system: "monitor", desktop: "monitor", wall: "monitor", phone: "devices", tablet: "devices",
  arrowright: "arrow", chevronright: "chevron", chevronup: "up", chevrondown: "down",
  "at a glance": "home", "people at home": "people", "coming up": "calendar", "things to do": "check",
  "home controls": "power", "rooms & devices": "spaces", "system health": "activity",
  "notifications & recent actions": "notifications", "talk with anima": "anima", "talk with sentry": "anima",
  "recent activity": "activity", "household interface": "settings", "create a room or zone": "plus",
  "household places": "spaces", "add a device": "plus", "discovered home assistant devices": "devices",
  "notification route": "notifications", "delivery boundary": "capabilities", "create an alert policy": "alerts",
  "edit alert policy": "edit", "configured policies": "capabilities", "alert inbox": "notifications",
  "create a scene": "scenes", "edit scene": "edit", "saved scenes": "scenes",
  "create an automation": "automations", "edit automation": "edit", "saved automations": "automations",
  "anima backups": "backups", "recovery boundary": "capabilities", "registered integrations": "integrations",
  "add a supported integration": "plus", boundary: "capabilities", "correct a preference": "edit",
  "add a household preference": "heart", "active household preferences": "preferences",
};

export type IconProps = Omit<SVGProps<SVGSVGElement>, "name" | "children"> & {
  /** Navigation labels (including 'Tasks & Calendar') or short action names. */
  name: string;
  size?: number;
  /** Omit for decorative icons next to visible text. Label icon-only buttons on the button itself. */
  label?: string;
  title?: string;
};

export function Icon({ name, size = 20, label, title, className = "", ...props }: IconProps) {
  const key = name.trim().toLowerCase();
  const resolved = aliases[key] ?? (Object.hasOwn(paths, key) ? key as IconName : "info");
  const accessibleLabel = label ?? title ?? props["aria-label"];
  return <svg {...props} className={`icon ${className}`} width={size} height={size} viewBox="0 0 24 24"
    fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round"
    role={accessibleLabel ? "img" : undefined} aria-label={accessibleLabel}
    aria-hidden={accessibleLabel || props["aria-labelledby"] ? undefined : true} focusable="false">
    {title && <title>{title}</title>}<path d={paths[resolved]} />
  </svg>;
}

export type VisualTone = "teal" | "sage" | "amber" | "rose" | "sky" | "muted";
export type MeterProps = {
  value: number | null | undefined;
  max: number;
  label: string;
  min?: number;
  tone?: VisualTone;
  valueLabel?: string;
  className?: string;
};

function measurement(value: MeterProps["value"], min: number, max: number) {
  if (typeof value !== "number" || !Number.isFinite(value) || !Number.isFinite(min)
    || !Number.isFinite(max) || max <= min || !Number.isFinite(max - min)) return null;
  const bounded = Math.min(max, Math.max(min, value));
  return { bounded, percent: (bounded - min) / (max - min) * 100, clipped: bounded !== value };
}

/** Unknown values have no numeric ARIA state and no fabricated zero fill. */
export function Meter({ value, max, min = 0, label, tone = "teal", valueLabel, className = "" }: MeterProps) {
  const data = measurement(value, min, max);
  const text = data ? valueLabel ?? `${value} / ${max}` : "Unavailable";
  const description = `${text}${data?.clipped ? " (outside display range)" : ""}`;
  return <div className={`meter visual-tone-${tone} ${className}`} data-available={Boolean(data)}>
    <div className="meter-heading"><span>{label}</span><strong>{description}</strong></div>
    <div className="meter-track" role={data ? "meter" : "img"} aria-label={label}
      aria-valuemin={data ? min : undefined} aria-valuemax={data ? max : undefined}
      aria-valuenow={data?.bounded} aria-valuetext={data ? description : undefined}
      {...(!data ? { "aria-label": `${label}: Unavailable` } : {})}>
      {data && <span className="meter-fill" style={{ width: `${data.percent}%` }} />}
    </div>
  </div>;
}

export type StatusRingProps = Omit<MeterProps, "max" | "min"> & {
  total: number;
  size?: number;
};

export function StatusRing({ value, total, label, tone = "teal", valueLabel, size = 112, className = "" }: StatusRingProps) {
  const data = measurement(value, 0, total);
  const text = data ? valueLabel ?? `${value} / ${total}` : "Unavailable";
  const description = `${text}${data?.clipped ? " (outside display range)" : ""}`;
  return <div className={`status-ring visual-tone-${tone} ${className}`} data-available={Boolean(data)}
    style={{ "--ring-size": `${Number.isFinite(size) ? Math.max(64, size) : 112}px` } as CSSProperties}>
    <div className="status-ring-graphic" role={data ? "meter" : "img"} aria-label={data ? label : `${label}: Unavailable`}
      aria-valuemin={data ? 0 : undefined} aria-valuemax={data ? total : undefined}
      aria-valuenow={data?.bounded} aria-valuetext={data ? description : undefined}>
      <svg viewBox="0 0 100 100" aria-hidden="true" focusable="false">
        <circle className="ring-track" cx="50" cy="50" r="42" />
        {data && data.percent > 0 && <circle className="ring-fill" cx="50" cy="50" r="42" pathLength="100"
          strokeDasharray={`${data.percent} 100`} transform="rotate(-90 50 50)" />}
      </svg>
      <strong className="ring-value" aria-hidden="true">{data ? valueLabel ?? value : "—"}</strong>
    </div>
    <span className="ring-label">{label}</span>
    <small className="ring-caption">{description}</small>
  </div>;
}

export type BarDatum = { label: string; value: number | null; tone?: VisualTone };
export type BarChartProps = { label: string; data: readonly BarDatum[]; unit?: string; className?: string };

/** Category bars share a zero baseline; missing and negative count values are explicitly unavailable. */
export function BarChart({ label, data, unit = "", className = "" }: BarChartProps) {
  const max = data.reduce((largest, item) => Number.isFinite(item.value) && item.value !== null
    ? Math.max(largest, item.value) : largest, 0);
  return <figure className={`bar-chart ${className}`}>
    <figcaption>{label}</figcaption>
    {data.length ? <div className="bar-chart-rows">{data.map((item, index) => <Meter key={`${item.label}-${index}`}
      label={item.label} value={item.value !== null && item.value >= 0 ? item.value : null}
      max={max || 1} valueLabel={`${item.value}${unit ? ` ${unit}` : ""}`} tone={item.tone} />)}</div>
      : <EmptyState icon="chart" title="No observations yet" />}
  </figure>;
}

export type SparklineProps = {
  label: string;
  values: readonly (number | null)[];
  unit?: string;
  tone?: VisualTone;
  className?: string;
};

/** Values are equally spaced observations, not inferred timestamps. Nulls break the line. */
export function Sparkline({ label, values, unit = "", tone = "teal", className = "" }: SparklineProps) {
  const finite = values.filter((value): value is number => value !== null && Number.isFinite(value));
  if (!finite.length) return <EmptyState icon="chart" title={label} description="No observations yet" className={className} />;
  const min = finite.reduce((a, b) => Math.min(a, b));
  const max = finite.reduce((a, b) => Math.max(a, b));
  // Scale first to avoid overflow for very large, finite observations.
  const scale = Math.max(Math.abs(min), Math.abs(max), 1);
  const range = max / scale - min / scale;
  let drawing = "";
  let connected = false;
  const dots: { x: number; y: number; index: number }[] = [];
  values.forEach((value, index) => {
    if (value === null || !Number.isFinite(value)) { connected = false; return; }
    const x = values.length === 1 ? 150 : 8 + index / (values.length - 1) * 284;
    const y = range === 0 ? 40 : 70 - ((value / scale - min / scale) / range) * 60;
    drawing += `${connected ? "L" : "M"}${x},${y} `;
    dots.push({ x, y, index }); connected = true;
  });
  return <figure className={`sparkline visual-tone-${tone} ${className}`}>
    <figcaption>{label}</figcaption>
    <svg viewBox="0 0 300 80" role="img" aria-label={`${label}: ${finite.length} observations; minimum ${min}${unit}, maximum ${max}${unit}`}>
      <path className="sparkline-guide" d="M8 70H292M8 40H292M8 10H292" />
      <path className="sparkline-line" d={drawing} />
      {dots.map(({ x, y, index }) => <circle key={index} cx={x} cy={y} r="2.5" className="sparkline-dot" />)}
    </svg>
    <div className="chart-range"><span>Min {min}{unit}</span><span>Max {max}{unit}</span></div>
    <details className="chart-values"><summary>View observations</summary><ol>{values.map((value, index) =>
      <li key={index}>{value === null || !Number.isFinite(value) ? "Unavailable" : `${value}${unit}`}</li>)}</ol></details>
  </figure>;
}

export type EmptyStateProps = { icon?: string; title: string; description?: string; children?: ReactNode; className?: string };
export function EmptyState({ icon = "spaces", title, description, children, className = "" }: EmptyStateProps) {
  return <div className={`empty-state ${className}`}><span className="empty-state-icon"><Icon name={icon} size={30} /></span>
    <strong>{title}</strong>{description && <p>{description}</p>}{children}</div>;
}
