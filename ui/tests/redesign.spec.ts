import { expect, test, type Page } from "@playwright/test";

// Browser contract fixtures: these tests do not claim a live household connection.
const widgets = ["status", "presence", "weather", "agenda", "tasks", "controls", "conversation", "activity", "household", "reports", "health"];
const settings = { version: 1, appearance: "night", accent: "ember", density: "comfortable", reduced_motion: true, text_scale: "normal", display_mode: "desktop", visible_widgets: widgets, widget_order: widgets };
const nav = ["Home", "Devices", "Spaces", "Scenes", "Automations", "Alerts", "Notifications", "Anima", "Tasks & Calendar", "Activity", "Capabilities", "Integrations", "Backups", "Preferences", "Settings"];
const home = {
  household: { name: "UI contract household", status: "CURRENT", summary: "Fixture household" },
  security: { status: "UNKNOWN", label: "Unknown" }, presence: { people: [] }, weather: { status: "UNAVAILABLE", summary: "No weather observation" },
  calendar: [], tasks: [], controls: [{ control_id: "lamp", label: "Reading lamp", state: "off" }],
  activity: [], voice: { status: "UNAVAILABLE", label: "Unavailable" },
  rooms: [{ place_id: "study", name: "Study", kind: "ROOM", devices: [{ device_id: "lamp", name: "Reading lamp", kind: "DEVICE", state: "off" }, { device_id: "sensor", name: "Room sensor", kind: "DEVICE", state: "UNKNOWN" }] }],
  notifications: [], reports: [], recent_actions: [], pending_approvals: [], health: { status: "CURRENT", summary: "Fixture Core", unavailable: [], degraded: [] },
};
const device = (id: string, name: string, mapped: boolean) => ({
  device_handle: id, external_object_kind: "device", present: true, state: "off", truth_status: "CURRENT", observed_at: "2026-09-06T12:00:00Z",
  metadata: { name, mapping_status: mapped ? "MAPPED" : "UNMAPPED", canonical_target_id: mapped ? id : null },
  capabilities: mapped ? [{ type: "power.set", label: "Power", writable: true, readable: true, state: "off", truth_status: "CURRENT" }] : [],
});
async function fixture(page: Page, connection: Record<string, unknown> | null = { configured: false, connected: false, state: "SETUP_REQUIRED", can_connect: true, setup_required: true, household_source: "sample" }) {
  const writes: { path: string; body: unknown }[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(); const path = new URL(request.url()).pathname;
    if (path === "/api/v1/events") { await route.abort(); return; }
    if (request.method() !== "GET") {
      writes.push({ path, body: request.postDataJSON() });
      await route.fulfill({ json: path === "/api/v1/conversation" ? { response: "Fixture reply", disposition: "RESPONSE" } : { status: "SUCCEEDED", operation: "fixture", detail: "Contract accepted" } }); return;
    }
    if (path === "/api/v1/connection" && connection === null) { await route.fulfill({ status: 503, json: { detail: "UNAVAILABLE" } }); return; }
    const data: Record<string, unknown> = {
      "/api/v1/setup/status": { state: "SETUP_REQUIRED", available: true },
      "/api/v1/bootstrap": { identity: { display_name: "Fixture", assurance: "OWNER" }, household: home.household, theme: settings, layout: settings, csrf_token: "fixture-csrf" },
      "/api/v1/home": home, "/api/v1/settings": { settings },
      "/api/v1/connection": connection,
      "/api/v1/devices": { status: "CURRENT", items: [device("lamp", "Reading lamp", true), device("new", "New light", false)] },
      "/api/v1/places": { items: [{ place_id: "household", name: "Household", kind: "HOUSEHOLD" }, { place_id: "study", name: "Study", kind: "ROOM", parent_id: "household" }] },
      "/api/v1/capabilities": { items: [{ id: "control", label: "Device control", state: "available" }, { id: "weather", label: "Weather", state: "unavailable" }] },
      "/api/v1/automations": { items: [{ automation_id: "rule", name: "Reading routine", trigger_resource_id: "lamp", trigger_state: "on", action_resource_id: "lamp", action_desired_on: false, enabled: true, version: 3, updated_at: "2026-09-06T12:00:00Z" }] },
    };
    await route.fulfill({ json: data[path] ?? { items: [], next_cursor: null } });
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Welcome,/ })).toBeVisible();
  return writes;
}
test("each section opens an editable assistant draft without sending", async ({ page }) => {
  const writes = await fixture(page);
  for (const section of nav) {
    await page.getByRole("navigation").getByRole("button", { name: section, exact: true }).click();
    const actions = page.getByLabel(`Assistant quick actions for ${section}`);
    await actions.getByRole("button").first().click();
    await expect(page.getByRole("heading", { name: "Talk with Anima" })).toBeVisible();
    await expect(page.getByLabel("Message Anima")).not.toHaveValue("");
    await expect(page.getByLabel("Message Anima")).toBeFocused();
    expect(writes).toHaveLength(0);
  }
});

test("every section fits the viewport with accessible navigation", async ({ page }, testInfo) => {
  await fixture(page);
  for (const section of nav) {
    const button = page.getByRole("navigation").getByRole("button", { name: section, exact: true });
    await button.click();
    await expect(button).toHaveAttribute("aria-current", "page");
    await expect(page.getByLabel(`${section} overview`, { exact: true })).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const content = await page.locator("main.content").boundingBox();
    const viewport = page.viewportSize()!;
    expect(content!.width).toBeGreaterThan(viewport.width * 0.55);
    if (viewport.width >= 834) expect(content!.y).toBeLessThan(100);
    await page.screenshot({ path: testInfo.outputPath(`${section.replaceAll(/[^a-z0-9]/gi, "-")}.png`), fullPage: true });
  }
});
test("device filters preserve explicit power payloads and observed selection", async ({ page }) => {
  const writes = await fixture(page);
  await page.getByRole("navigation").getByRole("button", { name: "Devices", exact: true }).click();
  await page.getByLabel("Search devices").fill("Reading");
  await expect(page.locator(".device-grid .device-row")).toHaveCount(1);
  await expect(page.getByRole("button", { name: "Turn Reading lamp off" })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Turn Reading lamp on" }).click();
  await expect.poll(() => writes.length).toBe(1);
  expect(writes[0]).toEqual({ path: "/api/v1/controls/lamp", body: { payload: { desired_on: true } } });
  await page.getByLabel("Search devices").fill("");
  await page.getByLabel("Device status").selectOption("new");
  await expect(page.locator(".device-grid .device-row")).toHaveCount(1);
  await expect(page.getByRole("button", { name: "Add to Anima" })).toBeVisible();
  await page.getByLabel("Device status").selectOption("all");
  await page.getByLabel("Filter by room").selectOption("study");
  await expect(page.locator(".device-grid .device-row")).toHaveCount(1);
});
test("connection setup CTA is explicit and snapshot charts use returned counts", async ({ page }) => {
  const writes = await fixture(page);
  await expect(page.getByRole("link", { name: "Connect Home Assistant", exact: true })).toHaveAttribute("href", "/auth/login?connect=1");
  await expect(page.getByRole("meter", { name: "Devices with on/off state" })).toHaveAttribute("aria-valuenow", "1");
  await expect(page.getByRole("meter", { name: "Devices with on/off state" })).toHaveAttribute("aria-valuemax", "2");
  await expect(page.getByRole("meter", { name: "Other / unknown state" })).toHaveAttribute("aria-valuenow", "1");
  expect(writes).toHaveLength(0);
});
test("unavailable connection status does not block the household UI or claim connected", async ({ page }) => {
  await fixture(page, null);
  await expect(page.getByText("Connection status unavailable", { exact: true })).toBeVisible();
  await expect(page.getByText("Home Assistant connected", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Connect Home Assistant", exact: true })).toHaveCount(0);
});
test("configured disconnected household is distinct from first-use setup", async ({ page }) => {
  await fixture(page, { configured: true, connected: false, state: "OFFLINE", can_connect: true, setup_required: false, household_source: "owner_connected" });
  await expect(page.getByText("Home Assistant disconnected", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Reconnect Home Assistant" })).toHaveAttribute("href", "/auth/login?connect=1");
});

test("connected household has a compact status and no reconnect CTA", async ({ page }) => {
  await fixture(page, { configured: true, connected: true, state: "ONLINE", can_connect: true, setup_required: false, household_source: "owner_connected" });
  const banner = page.getByRole("region", { name: "Home Assistant connection" });
  await expect(banner.getByText("Home Assistant connected", { exact: true })).toBeVisible();
  await expect(banner.getByRole("link")).toHaveCount(0);
  await expect(banner.locator(".connection-copy small")).toHaveCount(0);
  await expect(banner.getByRole("button", { name: "Refresh connection status" })).toBeVisible();
});
test("automation enable control retains complete versioned definition", async ({ page }) => {
  const writes = await fixture(page);
  await page.getByRole("navigation").getByRole("button", { name: "Automations", exact: true }).click();
  await page.getByRole("button", { name: "Disable", exact: true }).click();
  await expect.poll(() => writes.length).toBe(1);
  expect(writes[0]).toEqual({ path: "/api/v1/automations", body: { payload: { automation_id: "rule", expected_version: 3, name: "Reading routine", trigger_resource_id: "lamp", trigger_state: "on", action_resource_id: "lamp", action_desired_on: false, enabled: false } } });
});
test("ordinary response stays Anima-labeled until SENTRY disposition is observed", async ({ page }) => {
  const writes = await fixture(page);
  await page.getByRole("navigation").getByRole("button", { name: "Anima", exact: true }).click();
  await page.getByLabel("Message Anima").fill("Review my home");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.locator(".reply strong")).toHaveText("Anima");
  expect(writes[0]).toEqual({ path: "/api/v1/conversation", body: { text: "Review my home" } });
});
async function queueConversation(page: Page) {
  let posts = 0;
  await page.route("**/api/v1/conversation", async (route) => {
    posts += 1;
    await route.fulfill({ json: { response: "SENTRY received request and is reasoning", disposition: "QUEUED_FOR_SENTRY", request_id: "result-request" } });
  });
  await page.clock.install();
  await page.clock.pauseAt(new Date());
  await page.getByRole("navigation").getByRole("button", { name: "Anima", exact: true }).click();
  await page.getByLabel("Message Anima").fill("Synthetic result lookup");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.locator(".conversation")).toContainText("WAITING FOR SENTRY");
  return () => posts;
}

for (const status of [404, 401, 403]) {
  test(`result HTTP ${status} replaces stale acknowledgement and survives refresh without retry`, async ({ page }) => {
    await fixture(page);
    let gets = 0;
    await page.route("**/api/v1/conversation/result-request", async (route) => {
      gets += 1;
      await route.fulfill({ status, json: { detail: status === 401 ? "SESSION_EXPIRED" : "RESULT_NOT_ACCESSIBLE" } });
    });
    const posts = await queueConversation(page);
    await page.clock.runFor(1000);
    const alert = page.locator(".conversation").getByRole("alert");
    await expect(alert).toContainText(`HTTP ${status}`);
    await expect(page.locator(".reply")).toHaveCount(0);
    if (status === 401) await expect(alert.getByRole("link", { name: "Sign in again" })).toHaveAttribute("href", "/auth/login");
    const refreshed = page.waitForResponse("**/api/v1/home");
    await page.getByRole("button", { name: "Refresh connection status" }).click();
    await refreshed;
    await page.clock.runFor(5000);
    await expect(alert).toContainText(`HTTP ${status}`);
    expect(gets).toBe(1); expect(posts()).toBe(1);
  });
}

test("result transport failure retries only GET and displays recovered reply", async ({ page }) => {
  await fixture(page);
  let gets = 0;
  await page.route("**/api/v1/conversation/result-request", async (route) => {
    gets += 1;
    if (gets === 1) { await route.abort("connectionreset"); return; }
    await route.fulfill({ json: { request_id: "result-request", status: "COMPLETED", available: true, response: "Recovered actual result" } });
  });
  const posts = await queueConversation(page);
  await page.clock.runFor(1000);
  await expect(page.locator(".conversation").getByRole("alert")).toContainText("Retrying the result lookup only");
  await expect(page.locator(".reply")).toHaveCount(0);
  await page.clock.runFor(3000);
  await expect(page.locator(".reply")).toContainText("Recovered actual result");
  await expect(page.locator(".conversation").getByRole("alert")).toHaveCount(0);
  expect(gets).toBe(2); expect(posts()).toBe(1);
});

test("result arriving at 270 seconds is still polled without a second POST", async ({ page }) => {
  await fixture(page);
  let ready = false;
  await page.route("**/api/v1/conversation/result-request", async (route) => {
    await route.fulfill({ json: { request_id: "result-request", status: ready ? "COMPLETED" : "RUNNING", available: ready, response: ready ? "Late actual result" : null } });
  });
  const posts = await queueConversation(page);
  await page.clock.fastForward(120_000);
  await expect(page.locator(".conversation")).toContainText("WAITING FOR SENTRY");
  ready = true;
  await page.clock.fastForward(150_000);
  await expect(page.locator(".reply")).toContainText("Late actual result");
  expect(posts()).toBe(1);
});

test("result window expires at 300 seconds and stops GET polling", async ({ page }) => {
  await fixture(page);
  let gets = 0;
  await page.route("**/api/v1/conversation/result-request", async (route) => {
    gets += 1;
    await route.fulfill({ json: { request_id: "result-request", status: "RUNNING", available: false } });
  });
  const posts = await queueConversation(page);
  await page.clock.fastForward(299_000);
  await expect.poll(() => gets).toBe(1);
  await page.clock.runFor(1000);
  await expect(page.locator(".conversation").getByRole("alert")).toContainText("within 300 seconds");
  await expect(page.locator(".reply")).toHaveCount(0);
  const stoppedAt = gets;
  await page.clock.fastForward(30_000);
  expect(gets).toBe(stoppedAt); expect(posts()).toBe(1);
});

test("stalled result GET is aborted and retried without resubmission", async ({ page }) => {
  await fixture(page);
  let gets = 0;
  await page.route("**/api/v1/conversation/result-request", async (route) => {
    gets += 1;
    if (gets === 1) return; // Leave the intercepted GET pending until its AbortController fires.
    await route.fulfill({ json: { request_id: "result-request", status: "COMPLETED", available: true, response: "Reply after GET timeout" } });
  });
  const posts = await queueConversation(page);
  await page.clock.runFor(1000);
  await expect.poll(() => gets).toBe(1);
  await page.clock.runFor(10_000);
  await expect(page.locator(".conversation").getByRole("alert")).toContainText("Retrying the result lookup only");
  await page.clock.runFor(3000);
  await expect(page.locator(".reply")).toContainText("Reply after GET timeout");
  expect(gets).toBe(2); expect(posts()).toBe(1);
});

test("submission transport failure is never automatically retried", async ({ page }) => {
  await fixture(page);
  let posts = 0;
  await page.route("**/api/v1/conversation", async (route) => { posts += 1; await route.abort("connectionreset"); });
  await page.getByRole("navigation").getByRole("button", { name: "Anima", exact: true }).click();
  await page.getByLabel("Message Anima").fill("Synthetic failed submission");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.locator(".conversation").getByRole("alert")).toContainText("Nothing was resent");
  await page.getByRole("button", { name: "Refresh connection status" }).click();
  await expect(page.locator(".conversation").getByRole("alert")).toContainText("Nothing was resent");
  expect(posts).toBe(1);
});

test("unauthenticated first-use offers owner sign-in without credential fields", async ({ page }) => {
  await page.route("**/api/v1/**", async (route) => {
    const setup = new URL(route.request().url()).pathname === "/api/v1/setup/status";
    await route.fulfill({ status: setup ? 200 : 401, json: setup ? { state: "SETUP_REQUIRED", available: true } : { detail: "AUTHENTICATION_REQUIRED" } });
  });
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Connect your Home Assistant" })).toHaveAttribute("href", "/auth/login?connect=1");
  await expect(page.getByRole("link", { name: "Continue with existing Home Assistant" })).toHaveAttribute("href", "/auth/login");
  await expect(page.locator("input, textarea")).toHaveCount(0);
});

test("mutation outcome is visible while an unrelated snapshot request is stalled", async ({ page }) => {
  await fixture(page);
  let release!: () => void;
  const stalled = new Promise<void>((resolve) => { release = resolve; });
  let started = false;
  await page.route("**/api/v1/home", async (route) => {
    started = true;
    await stalled;
    await route.fulfill({ json: home });
  });
  try {
    await page.getByRole("navigation").getByRole("button", { name: "Automations", exact: true }).click();
    await page.getByRole("button", { name: "Disable", exact: true }).click();
    await expect(page.getByRole("status").filter({ hasText: "SUCCEEDED" })).toBeVisible();
    await expect.poll(() => started).toBe(true);
  } finally { release(); }
});

test("partial refresh keeps newly commissioned devices when Home times out", async ({ page }) => {
  const writes = await fixture(page);
  await page.getByRole("navigation").getByRole("button", { name: "Devices", exact: true }).click();
  const commissioned = page.locator(".summary-card").filter({ hasText: "Commissioned" }).locator(".summary-value");
  await expect(commissioned).toHaveText("1");
  await page.clock.install(); await page.clock.pauseAt(new Date());
  await page.route("**/api/v1/home", () => {});
  await page.route("**/api/v1/devices", (route) => route.fulfill({ json: { status: "CURRENT", items: [device("lamp", "Reading lamp", true), device("new", "New light", true)] } }));
  const devicesRead = page.waitForResponse("**/api/v1/devices");
  await page.getByRole("button", { name: "Refresh connection status" }).click();
  await devicesRead;
  await page.clock.runFor(10_000);
  await expect(commissioned).toHaveText("2");
  await expect(page.getByRole("alert")).toContainText("Home (/api/v1/home) timed out");
  expect(writes).toHaveLength(0);
});

test("late snapshot 401 clears protected arrays and late reads cannot restore them", async ({ page }) => {
  await fixture(page);
  let releaseAuth!: () => void;
  let releaseDevices!: () => void;
  const authGate = new Promise<void>((resolve) => { releaseAuth = resolve; });
  const devicesGate = new Promise<void>((resolve) => { releaseDevices = resolve; });
  await page.route("**/api/v1/preferences", async (route) => { await authGate; await route.fulfill({ status: 401, json: { detail: "SESSION_EXPIRED" } }); });
  await page.route("**/api/v1/devices", async (route) => { await devicesGate; await route.fulfill({ json: { items: [device("late", "Late protected device", true)] } }); });
  const bootstrapRead = page.waitForResponse("**/api/v1/bootstrap");
  await page.getByRole("button", { name: "Refresh connection status" }).click();
  await bootstrapRead;
  releaseAuth();
  await expect(page.getByRole("heading", { name: "Reconnect your household" })).toBeVisible();
  releaseDevices();
  await expect(page.getByRole("navigation")).toHaveCount(0);
  await expect(page.getByText("Late protected device")).toHaveCount(0);
  // Recover authentication but leave these sections unavailable: no prior-household arrays may remain.
  await page.route("**/api/v1/preferences", (route) => route.fulfill({ json: { items: [] } }));
  for (const path of ["devices", "places", "automations", "capabilities", "integrations"]) {
    await page.route(`**/api/v1/${path}`, (route) => route.fulfill({ status: 503, json: { detail: "UNAVAILABLE" } }));
  }
  await page.evaluate(() => window.dispatchEvent(new Event("pageshow")));
  await expect(page.getByRole("navigation")).toBeVisible();
  await page.getByRole("navigation").getByRole("button", { name: "Devices", exact: true }).click();
  await expect(page.locator(".device-grid .device-row")).toHaveCount(0);
  await expect(page.locator(".summary-card").filter({ hasText: "Commissioned" }).locator(".summary-value")).toHaveText("0");
  await page.getByRole("navigation").getByRole("button", { name: "Spaces", exact: true }).click();
  await expect(page.locator(".space-row")).toHaveCount(0);
  await page.getByRole("navigation").getByRole("button", { name: "Automations", exact: true }).click();
  await expect(page.getByText("Reading routine", { exact: true })).toHaveCount(0);
});

test("failed bootstrap prevents successful protected reads from being committed", async ({ page }) => {
  await fixture(page);
  await page.route("**/api/v1/bootstrap", (route) => route.fulfill({ status: 503, json: { detail: "UNAVAILABLE" } }));
  await page.route("**/api/v1/devices", (route) => route.fulfill({ json: { items: [device("unverified", "Unverified session device", true)] } }));
  await page.getByRole("button", { name: "Refresh connection status" }).click();
  await expect(page.getByRole("alert")).toContainText("Session (/api/v1/bootstrap) unavailable");
  await page.getByRole("navigation").getByRole("button", { name: "Devices", exact: true }).click();
  await expect(page.getByText("Unverified session device", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Reading lamp", { exact: true })).toBeVisible();
});

test("hidden tabs close SSE and foreground resumes with one refreshed snapshot", async ({ page }) => {
  await page.addInitScript(() => {
    const testWindow = window as unknown as {
      streams: { closed: boolean; close(): void }[];
      setHidden: (hidden: boolean) => void;
      EventSource: unknown;
    };
    testWindow.streams = [];
    testWindow.EventSource = class extends EventTarget {
      closed = false;
      constructor() { super(); testWindow.streams.push(this); }
      close() { this.closed = true; }
    };
    let hidden = false;
    Object.defineProperty(document, "hidden", { get: () => hidden, configurable: true });
    Object.defineProperty(document, "visibilityState", { get: () => hidden ? "hidden" : "visible", configurable: true });
    testWindow.setHidden = (value) => { hidden = value; document.dispatchEvent(new Event("visibilitychange")); };
  });
  await fixture(page);
  const activeStreams = () => page.evaluate(() => (window as unknown as { streams: { closed: boolean }[] }).streams.filter((stream) => !stream.closed).length);
  await expect.poll(activeStreams).toBe(1);
  await page.evaluate(() => (window as unknown as { setHidden: (value: boolean) => void }).setHidden(true));
  await expect.poll(activeStreams).toBe(0);
  let snapshots = 0;
  page.on("request", (request) => { if (new URL(request.url()).pathname === "/api/v1/home") snapshots += 1; });
  await page.evaluate(() => (window as unknown as { setHidden: (value: boolean) => void }).setHidden(false));
  await expect.poll(activeStreams).toBe(1);
  await expect.poll(() => snapshots).toBe(1);
  await expect(page.getByRole("heading", { name: /Welcome,/ })).toBeVisible();
});
