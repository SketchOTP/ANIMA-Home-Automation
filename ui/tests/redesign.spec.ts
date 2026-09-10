import { expect, test, type Page } from "@playwright/test";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";

// Browser contract fixtures: these tests do not claim a live household connection.
const widgets = ["status", "presence", "weather", "agenda", "tasks", "controls", "conversation", "activity", "household", "reports", "health"];
const settings = { version: 1, appearance: "night", accent: "ember", density: "comfortable", reduced_motion: true, text_scale: "normal", display_mode: "desktop", visible_widgets: widgets, widget_order: widgets };
const nav = ["Home", "Devices", "Spaces", "Routines", "Scenes", "Automations", "SENTRY", "Alerts", "Tasks & Calendar", "Activity", "Users", "Connections", "Backups", "Preferences", "Settings"];
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
      await route.fulfill({ json: path === "/api/v1/conversation" ? { request_id: "request-1", response: "SENTRY received the request.", disposition: "QUEUED_FOR_SENTRY" } : { status: "SUCCEEDED", operation: "fixture", detail: "Contract accepted" } }); return;
    }
    if (path === "/api/v1/connection" && connection === null) { await route.fulfill({ status: 503, json: { detail: "UNAVAILABLE" } }); return; }
    const data: Record<string, unknown> = {
      "/api/v1/family-routines": { items: [], next_cursor: null, members: [], places: [], can_edit: false },
      "/api/v1/setup/status": { state: "SETUP_REQUIRED", available: true },
      "/api/v1/bootstrap": { identity: { display_name: "Fixture", assurance: "OWNER" }, household: home.household, theme: settings, layout: settings, csrf_token: "fixture-csrf" },
      "/api/v1/home": home, "/api/v1/settings": { settings },
      "/api/v1/connection": connection,
      "/api/v1/devices": { status: "CURRENT", items: [device("lamp", "Reading lamp", true), device("new", "New light", false)] },
      "/api/v1/places": { items: [{ place_id: "household", name: "Household", kind: "HOUSEHOLD" }, { place_id: "study", name: "Study", kind: "ROOM", parent_id: "household" }] },
      "/api/v1/capabilities": { items: [{ id: "control", label: "Device control", state: "available" }, { id: "weather", label: "Weather", state: "unavailable" }] },
      "/api/v1/automations": { items: [{ automation_id: "rule", name: "Reading routine", trigger_resource_id: "lamp", trigger_state: "on", action_resource_id: "lamp", action_desired_on: false, enabled: true, version: 3, updated_at: "2026-09-06T12:00:00Z" }] },
      "/api/v1/initiative": { status: "SUCCEEDED", authority: "NONE", can_edit: true, config_version: null, timezone: "America/New_York", config: { learning_days: 3, routine_review_days: 3, daily_review_enabled: true, routine_review_enabled: true, proactive_enabled: false, always_notify: [], device_notifications: [] }, readiness: { ready: false, observed_local_days: 0, required_days: 3, first_observed_at: null, last_observed_at: null, elapsed_seconds: 0, required_elapsed_seconds: 259200, evidence_status: "SUCCEEDED", truncated: false }, proactive_eligible: false, scheduling: { status: "SCHEDULED", tasks: [] }, learning: { evidence_events: 0, candidate_count: 0, candidate_types: [], candidates: [], last_review: null, review_count: 0, pending_review_count: 0, gaps: ["No repeated qualified pattern meets the bounded candidate threshold."] } },
      "/api/v1/initiative/suggestions": { status: "SUCCEEDED", items: [], next_cursor: null },
      "/api/v1/users": { items: [{ person_id: "00000000-0000-0000-0000-000000000042", name: "Fixture User", role: "owner", access_level: "UNRESTRICTED", sentry_profile_id: null, sentry_profile_sample_count: null, sentry_onboarding_state: "NOT_STARTED", wifi_macs: [] }] },
      "/api/v1/conversation/request-1": { request_id: "request-1", status: "COMPLETED", lifecycle: "COMPLETED", response: "Fixture reply", available: true },
    };
    await route.fulfill({ json: data[path] ?? { items: [], next_cursor: null } });
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Welcome,/ })).toBeVisible();
  return writes;
}
test("assistant shortcuts prepare SENTRY chat without sending", async ({ page }) => {
  const writes = await fixture(page);
  for (const section of ["Home", "Devices", "Spaces", "Scenes", "Automations", "Alerts", "SENTRY", "Tasks & Calendar", "Activity", "Connections", "Backups", "Preferences", "Settings"]) {
    await page.getByRole("navigation").getByRole("button", { name: section, exact: true }).click();
    const actions = page.getByLabel(`Assistant quick actions for ${section}`);
    await actions.getByRole("button").first().click();
    await expect(page.getByRole("heading", { name: "SENTRY owner operations" })).toBeVisible();
    await expect(page.getByLabel("Tell SENTRY what to do")).not.toHaveValue("");
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

test("owner page explanations match the controls and boundaries actually shown", async ({ page }) => {
  await fixture(page);
  const pages: Array<[string, string, string[]]> = [
    ["Routines", "Routines records schedules and expectations", ["Add family routine", "Manage household users", "Saved family routines", "Household presence"]],
    ["Automations", "Automations are saved rules", ["Create an automation", "Saved automations"]],
    ["SENTRY", "Use SENTRY to describe a household request", ["SENTRY owner operations", "Tell SENTRY what to do"]],
    ["Alerts", "Alerts controls which household events deserve attention", ["Advanced event rule", "Alert inbox", "Notification route"]],
    ["Tasks & Calendar", "Tasks are durable reminders", ["Tasks", "Create task", "Calendar", "Create event"]],
    ["Activity", "Activity is a read-only view", ["Recent activity"]],
    ["Users", "Users manages the people ANIMA knows about", ["Add household user", "Household users"]],
    ["Connections", "Connections shows ANIMA's registered services", ["Ring notifications", "Vendor app notifications", "Registered integrations", "Capabilities"]],
    ["Backups", "Backups creates server-owned snapshots", ["ANIMA backups", "Recovery boundary"]],
    ["Preferences", "Preferences stores household-wide and person-specific guidance", ["Add a preference", "SENTRY initiative", "Memory · Knowledge base"]],
    ["Settings", "Settings controls how the ANIMA interface looks", ["Household interface", "Save interface settings", "SENTRY voice"]],
  ];
  for (const [section, description, controls] of pages) {
    await page.getByRole("navigation").getByRole("button", { name: section, exact: true }).click();
    await expect(page.locator(".section-description")).toContainText(description);
    for (const control of controls) await expect(page.getByText(control, { exact: true }).first()).toBeVisible();
  }
});

test("Users keeps an in-progress Wi-Fi MAC edit stable across background refresh", async ({ page }) => {
  await fixture(page);
  await page.getByRole("navigation").getByRole("button", { name: "Users", exact: true }).click();
  await page.getByRole("button", { name: "Edit user" }).click();
  const macs = page.getByLabel("Associated Wi-Fi MAC addresses");
  const value = "aa:bb:cc:dd:ee:ff\n11:22:33:44:55:66";
  await macs.fill(value);
  await macs.focus();
  await macs.evaluate((node) => (node as HTMLTextAreaElement).setSelectionRange(5, 5));
  await page.evaluate(() => {
    window.dispatchEvent(new Event("blur"));
    window.dispatchEvent(new Event("focus"));
  });
  await page.waitForTimeout(100);
  await expect(macs).toHaveValue(value);
  await expect.poll(() => macs.evaluate((node) => ({
    active: document.activeElement === node,
    start: (node as HTMLTextAreaElement).selectionStart,
    end: (node as HTMLTextAreaElement).selectionEnd,
  }))).toEqual({ active: true, start: 5, end: 5 });
});

test("notification-only connections are not offered as On Off automation triggers", async ({ page }) => {
  await fixture(page);
  await page.route("**/api/v1/devices", (route) => route.fulfill({ json: { status: "CURRENT", items: [
    device("lamp", "Reading lamp", true),
    { ...device("wansview", "Driveway camera alert", true), metadata: { name: "Driveway camera alert", mapping_status: "MAPPED", canonical_target_id: "wansview", source_kind: "notification_resource" }, capabilities: [] },
  ] } }));
  await page.reload();
  await page.getByRole("navigation").getByRole("button", { name: "Automations", exact: true }).click();
  await expect(page.getByLabel("When this device is").getByRole("option", { name: "Reading lamp" })).toHaveCount(1);
  await expect(page.getByLabel("When this device is").getByRole("option", { name: "Driveway camera alert" })).toHaveCount(0);
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
test("scene workflow explains saved states and toggles the durable enabled state", async ({ page }) => {
  await fixture(page);
  let scene = { scene_id: "scene-1", name: "Evening lights", steps: [{ resource_id: "lamp", desired_on: true }], enabled: true, version: 3, updated_at: "2026-09-08T12:00:00Z" };
  let updatePayload: Record<string, unknown> | null = null;
  await page.route("**/api/v1/scenes", async (route) => {
    const request = route.request();
    if (request.method() === "GET") { await route.fulfill({ json: { items: [scene] } }); return; }
    updatePayload = request.postDataJSON().payload as Record<string, unknown>;
    scene = { ...scene, enabled: Boolean(updatePayload.enabled), version: scene.version + 1 };
    await route.fulfill({ json: { status: "SUCCEEDED", operation: "scene.update", result: { scene } } });
  });
  await page.reload();
  await page.getByRole("navigation").getByRole("button", { name: "Scenes", exact: true }).click();
  await expect(page.getByLabel("Scenes overview")).toContainText("reusable presets");
  await expect(page.getByText("Saving the scene does not change any devices.")).toBeVisible();
  const row = page.getByRole("listitem").filter({ hasText: "Evening lights" });
  await expect(row.getByRole("button", { name: "Apply scene" })).toBeEnabled();
  await row.getByRole("button", { name: "Disable" }).click();
  await expect.poll(() => updatePayload).toEqual({ scene_id: "scene-1", expected_version: 3, name: "Evening lights", steps: [{ resource_id: "lamp", desired_on: true }], enabled: false });
  await expect(row.getByText("DISABLED", { exact: true })).toBeVisible();
  await expect(row.getByRole("button", { name: "Apply scene" })).toBeDisabled();
});
test("owner can set device alert behavior without leaving the device page", async ({ page }) => {
  const writes = await fixture(page);
  await page.getByRole("navigation").getByRole("button", { name: "Devices", exact: true }).click();
  await page.getByLabel("Alert behavior for Reading lamp").selectOption("TIME_WINDOW");
  const card = page.locator(".notification-device-card").filter({ hasText: "Reading lamp" });
  await card.getByLabel("From").fill("00:00");
  await card.getByLabel("Until").fill("05:00");
  await card.getByRole("button", { name: "Save alert setting" }).click();
  await expect.poll(() => writes.filter(item => item.path === "/api/v1/initiative/configure").length).toBe(1);
  const saved = writes.find(item => item.path === "/api/v1/initiative/configure")?.body as { payload: { device_notifications: { resource_id: string; mode: string }[] } };
  expect(saved.payload.device_notifications).toContainEqual(expect.objectContaining({ resource_id: "lamp", mode: "TIME_WINDOW" }));
});
for (const source of ["projection", "rooms fallback"]) {
  test(`canonical ${source} name replaces stale provider labels in devices manage and alerts`, async ({ page }) => {
    const writes = await fixture(page);
    const canonicalName = "Kitchen SenseGuard";
    await page.route("**/api/v1/devices", route => route.fulfill({ json: { items: [{
      ...device("lamp", "Old Basement provider name", true),
      ...(source === "projection" ? { canonical_name: canonicalName } : {}),
      metadata: { name: "Old Basement provider name", name_by_user: "Old Basement override", mapping_status: "MAPPED", canonical_target_id: "lamp" },
    }] } }));
    await page.route("**/api/v1/home", route => route.fulfill({ json: { ...home, rooms: [{ ...home.rooms[0], devices: [{ ...home.rooms[0].devices[0], name: source === "projection" ? "Older canonical snapshot" : canonicalName }] }] } }));
    await page.reload();
    await page.getByRole("navigation").getByRole("button", { name: "Devices", exact: true }).click();
    await expect(page.locator(".device-row strong")).toHaveText(canonicalName);
    await page.getByLabel("Search devices").fill("Kitchen");
    await expect(page.locator(".device-row")).toHaveCount(1);
    await page.getByRole("button", { name: "Manage", exact: true }).click();
    await expect(page.getByLabel("Display name", { exact: true })).toHaveValue(canonicalName);
    await page.getByRole("button", { name: "Save device", exact: true }).click();
    await expect.poll(() => writes.length).toBe(2);
    expect(writes).toEqual([
      { path: "/api/v1/devices/rename", body: { payload: { resource_id: "lamp", name: canonicalName } } },
      { path: "/api/v1/devices/reassign", body: { payload: { resource_id: "lamp", place_id: "study" } } },
    ]);
    await page.getByRole("navigation").getByRole("button", { name: "Alerts", exact: true }).click();
    await expect(page.getByRole("option", { name: canonicalName, exact: true })).toHaveAttribute("value", "lamp");
    await expect(page.getByRole("option", { name: /Old Basement/ })).toHaveCount(0);
  });
}

test("stale contact keeps historical report separate from current state and collapses diagnostics", async ({ page }, testInfo) => {
  await fixture(page, { configured: true, connected: true, state: "ONLINE", can_connect: true, setup_required: false, household_source: "owner_connected" });
  const historical = { last_reported_state: "CLOSED", last_reported_at: "2026-09-06T19:49:00Z", last_reported_source: "ANIMA_TRUTH" };
  const contact = { type: "state.read", label: "Contact diagnostic", readable: true, writable: false, state: "STALE", truth_status: "STALE", observed_at: "2026-09-06T20:12:00Z", ...historical };
  const capabilities = [contact, ...Array.from({ length: 5 }, (_, index) => ({ type: "state.read", label: `Diagnostic ${index + 1}`, readable: true, writable: false, state: "UNKNOWN", truth_status: "UNKNOWN" }))];
  await page.route("**/api/v1/devices", route => route.fulfill({ json: { items: [{ ...device("lamp", "Old provider name", true), canonical_name: "Kitchen SenseGuard", state: "STALE", truth_status: "STALE", observed_at: contact.observed_at, ...historical, capabilities }] } }));
  await page.reload();
  await page.getByRole("navigation").getByRole("button", { name: "Devices", exact: true }).click();
  const row = page.locator(".device-row");
  await expect(row.getByText("Current state: UNKNOWN", { exact: true })).toBeVisible();
  await expect(row.locator(":scope > span > small").filter({ hasText: /^Truth:/ })).toHaveText("Truth: STALE");
  const lastReport = row.locator(":scope > span > small").filter({ hasText: /^Last reported:/ });
  await expect(lastReport).toContainText("Last reported: CLOSED");
  await expect(lastReport).toContainText("ANIMA Truth · not current");
  await expect(lastReport.locator("time")).toHaveAttribute("datetime", historical.last_reported_at);
  await expect(page.getByText("Home Assistant connected", { exact: true })).toBeVisible();
  await expect(row).not.toContainText(/offline|disconnected/i);
  await expect(row.getByText("Current state: CLOSED", { exact: true })).toHaveCount(0);
  const details = row.locator("details");
  await expect(details).toHaveAccessibleName("Capabilities for Kitchen SenseGuard");
  await expect(details).toHaveJSProperty("open", false);
  await expect(details.locator(".capability-chip").filter({ hasText: "Contact diagnostic" })).not.toBeVisible();
  const collapsedHeight = (await row.boundingBox())!.height;
  await page.screenshot({ path: testInfo.outputPath("stale-contact-collapsed.png"), fullPage: true });
  await details.locator("summary").focus(); await details.locator("summary").press("Enter");
  await expect(details).toHaveJSProperty("open", true);
  await expect(details.locator(".capability-chip").filter({ hasText: "Contact diagnostic" })).toBeVisible();
  await expect(details.locator(".capability-chip")).toHaveCount(6);
  expect((await row.boundingBox())!.height).toBeGreaterThan(collapsedHeight);
  await page.screenshot({ path: testInfo.outputPath("stale-contact-expanded.png"), fullPage: true });
});

for (const status of ["SUCCEEDED", "POLICY_DENIED"]) {
  test(`capability sync preserves canonical identity and reports ${status} without duplicate submission`, async ({ page }) => {
    const writes = await fixture(page);
    let homeReads = 0;
    await page.route("**/api/v1/home", async (route) => {
      homeReads += 1;
      await route.fulfill({ json: { ...home, rooms: [
        { place_id: "draft-room", name: "Draft room", kind: "ROOM", devices: [] },
        { place_id: "canonical-room", name: "Kitchen", kind: "ROOM", devices: [{ device_id: "lamp", name: "Canonical SenseGuard", kind: "DEVICE", state: "UNKNOWN" }] },
      ] } });
    });
    await page.route("**/api/v1/devices", (route) => route.fulfill({ json: { items: [{ ...device("lamp", "Stale provider name", true), capabilities: [], metadata: { name: "Stale provider name", name_by_user: "Stale provider override", mapping_status: "MAPPED", canonical_target_id: "lamp" } }] } }));
    let finish!: () => void;
    const pending = new Promise<void>((resolve) => { finish = resolve; });
    await page.route("**/api/v1/devices/commission", async (route) => {
      writes.push({ path: new URL(route.request().url()).pathname, body: route.request().postDataJSON() });
      await pending;
      await route.fulfill({ json: { status, operation: "commission_device", detail: `Capability sync ${status}` } });
    });
    await page.reload();
    await page.getByRole("navigation").getByRole("button", { name: "Devices", exact: true }).click();
    await page.getByRole("button", { name: "Manage", exact: true }).click();
    await page.getByLabel("Display name", { exact: true }).fill("Unsaved rename");
    await page.getByRole("combobox", { name: "Room", exact: true }).selectOption("draft-room");
    const before = homeReads;
    await page.getByRole("button", { name: "Sync capabilities", exact: true }).click();
    await expect(page.getByRole("button", { name: "Syncing capabilities…", exact: true })).toBeDisabled();
    await expect.poll(() => writes.length).toBe(1);
    expect(writes[0]).toEqual({ path: "/api/v1/devices/commission", body: { payload: { device_handle: "lamp", name: "Canonical SenseGuard", place_id: "canonical-room" } } });
    await expect(page.getByText(`Capability sync ${status}`, { exact: true })).toHaveCount(0);
    finish();
    await expect(page.getByText(`Capability sync ${status}`, { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sync capabilities", exact: true })).toBeEnabled();
    await expect.poll(() => homeReads).toBeGreaterThan(before);
    await expect(page.getByLabel("Display name", { exact: true })).toHaveValue("Unsaved rename");
    expect(writes).toHaveLength(1);
  });
}

for (const mapping of ["missing", "ambiguous", "unnamed", "household"]) {
  test(`capability sync refuses ${mapping} canonical placement without a default room`, async ({ page }) => {
    const writes = await fixture(page);
    const canonicalRoom = home.rooms[0];
    const rooms = mapping === "missing" ? [{ ...canonicalRoom, devices: [] }]
      : mapping === "ambiguous" ? [canonicalRoom, { ...canonicalRoom, place_id: "other", name: "Other room" }]
      : mapping === "unnamed" ? [{ ...canonicalRoom, devices: [{ ...canonicalRoom.devices[0], name: "" }] }]
      : [{ ...canonicalRoom, kind: "HOUSEHOLD" }];
    await page.route("**/api/v1/home", (route) => route.fulfill({ json: { ...home, rooms } }));
    await page.reload();
    await page.getByRole("navigation").getByRole("button", { name: "Devices", exact: true }).click();
    const sync = page.getByRole("button", { name: "Sync capabilities", exact: true });
    await expect(sync).toHaveCount(1);
    await expect(sync).toBeDisabled();
    await expect(sync).toHaveAccessibleDescription("Cannot sync: canonical device name or room mapping is missing or ambiguous. Refresh household data first.");
    await expect(page.getByText(/Cannot sync: canonical device name or room mapping/)).toBeVisible();
    expect(writes).toHaveLength(0);
  });
}

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
test("SENTRY chat submits through the governed queue and polls the live result", async ({ page }) => {
  const writes = await fixture(page);
  await page.getByRole("navigation").getByRole("button", { name: "SENTRY", exact: true }).click();
  await page.getByLabel("Tell SENTRY what to do").fill("Create a safe household task");
  await page.getByRole("button", { name: "Send to SENTRY", exact: true }).click();
  await expect(page.getByText("Fixture reply", { exact: true })).toBeVisible();
  await expect.poll(() => writes.filter(item => item.path === "/api/v1/conversation").length).toBe(1);
  expect(writes.find(item => item.path === "/api/v1/conversation")?.body).toEqual({ text: "Create a safe household task" });
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

test("configured household automatically resumes through existing Home Assistant identity", async ({ page }) => {
  let loginRequests = 0;
  await page.route("**/api/v1/**", async (route) => {
    const setup = new URL(route.request().url()).pathname === "/api/v1/setup/status";
    await route.fulfill({ status: setup ? 200 : 401, json: setup ? { state: "ONLINE", available: true } : { detail: "AUTHENTICATION_REQUIRED" } });
  });
  await page.route("**/auth/login", async (route) => {
    loginRequests += 1;
    await route.fulfill({ contentType: "text/html", body: "ANIMA OAuth continuation" });
  });

  await page.goto("/");

  await expect.poll(() => loginRequests).toBe(1);
  await expect(page.getByText("ANIMA OAuth continuation", { exact: true })).toBeVisible();
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
  await expect(page.locator(".device-grid").getByText("Reading lamp", { exact: true })).toBeVisible();
});

test("calendar save uses the authoritative event and version without waiting for task reads", async ({ page }) => {
  await fixture(page);
  const initial = { event_id: "calendar-fixture", title: "Original appointment", start_at: "2026-09-08T12:00:00Z", end_at: "2026-09-08T13:00:00Z", status: "ACTIVE", version: 1 };
  await page.route("**/api/v1/calendar?*", (route) => route.fulfill({ json: { items: [initial], next_cursor: null } }));
  await page.getByRole("navigation").getByRole("button", { name: "Tasks & Calendar", exact: true }).click();
  const row = page.getByRole("listitem").filter({ hasText: initial.title });
  await expect(row).toBeVisible();
  let taskReads = 0;
  await page.route("**/api/v1/tasks?*", () => { taskReads += 1; });
  const commands: { path: string; payload: Record<string, unknown> }[] = [];
  await page.route("**/api/v1/calendar/calendar-fixture/*", async (route) => {
    const path = new URL(route.request().url()).pathname;
    commands.push({ path, payload: route.request().postDataJSON().payload });
    await route.fulfill({ json: { status: "SUCCEEDED", operation: "calendar.save", result: { event: { ...initial, title: "Authoritative saved appointment", status: path.endsWith("/cancel") ? "CANCELLED" : "ACTIVE", version: path.endsWith("/cancel") ? 3 : 2 } } } });
  });
  await row.getByRole("button", { name: "Edit", exact: true }).click();
  await page.locator("form.edit-form").getByLabel("Title", { exact: true }).fill("Submitted edit");
  await page.getByRole("button", { name: "Save edit" }).click();
  await expect(page.locator("form.edit-form")).toHaveCount(0);
  const saved = page.getByRole("listitem").filter({ hasText: "Authoritative saved appointment" });
  await expect(saved).toBeVisible();
  await saved.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(saved).toContainText("CANCELLED");
  expect(commands).toHaveLength(2);
  expect(commands[0].payload.expected_version).toBe(1);
  expect(commands[1].payload.expected_version).toBe(2);
  await expect.poll(() => taskReads).toBeGreaterThan(0);
});

test("initial visible unfocused view loads household without a stream and focus enables updates", async ({ page }) => {
  await page.addInitScript(() => {
    let focused = false;
    Object.defineProperty(document, "hasFocus", { value: () => focused, configurable: true });
    const state = window as unknown as { streams: { closed: boolean }[]; focusView: () => void };
    state.streams = [];
    window.EventSource = class extends EventTarget {
      closed = false;
      constructor() { super(); state.streams.push(this); }
      close() { this.closed = true; }
    } as unknown as typeof EventSource;
    state.focusView = () => { focused = true; window.dispatchEvent(new Event("focus")); };
  });
  let snapshots = 0;
  page.on("request", request => { if (new URL(request.url()).pathname === "/api/v1/bootstrap") snapshots++; });
  const writes = await fixture(page);
  await expect(page.getByRole("heading", { name: /Welcome,/ })).toBeVisible();
  expect(await page.evaluate(() => document.hasFocus())).toBe(false);
  const streamCount = () => page.evaluate(() => (window as unknown as { streams: { closed: boolean }[] }).streams.filter(stream => !stream.closed).length);
  expect(await streamCount()).toBe(0);
  await page.clock.install(); await page.clock.pauseAt(new Date());
  await page.clock.runFor(30000);
  expect(snapshots).toBe(1);
  await page.evaluate(() => (window as unknown as { focusView: () => void }).focusView());
  await expect.poll(() => snapshots).toBe(2);
  await expect.poll(streamCount).toBe(1);
  expect(writes).toHaveLength(0);
});

test("visible but unfocused views close streams and defer bounded error fallback until focus", async ({ page }) => {
  await page.addInitScript(() => {
    let focused = true;
    Object.defineProperty(document, "hasFocus", { value: () => focused, configurable: true });
    const state = window as unknown as { streams: { closed: boolean; onerror: (() => void) | null; close(): void }[]; setFocused: (value: boolean) => void };
    state.streams = [];
    window.EventSource = class extends EventTarget {
      closed = false;
      onerror = null;
      constructor() { super(); state.streams.push(this); }
      close() { this.closed = true; }
    } as unknown as typeof EventSource;
    state.setFocused = (value) => { focused = value; window.dispatchEvent(new Event(value ? "focus" : "blur")); };
  });
  await fixture(page);
  await page.clock.install(); await page.clock.pauseAt(new Date());
  const state = () => page.evaluate(() => {
    const streams = (window as unknown as { streams: { closed: boolean }[] }).streams;
    return { total: streams.length, active: streams.filter(stream => !stream.closed).length };
  });
  await expect.poll(state).toEqual({ total: 1, active: 1 });
  let snapshots = 0;
  page.on("request", request => { if (new URL(request.url()).pathname === "/api/v1/bootstrap") snapshots++; });
  await page.evaluate(() => (window as unknown as { streams: { onerror: () => void }[] }).streams[0].onerror());
  await expect.poll(state).toEqual({ total: 1, active: 0 });
  await page.clock.runFor(14900);
  expect(snapshots).toBe(0);
  await page.clock.runFor(100);
  await expect.poll(() => snapshots).toBe(1);
  await expect.poll(state).toEqual({ total: 2, active: 1 });
  await page.evaluate(() => (window as unknown as { setFocused: (value: boolean) => void }).setFocused(false));
  await expect.poll(state).toEqual({ total: 2, active: 0 });
  await page.clock.runFor(60000);
  expect(snapshots).toBe(1);
  await page.evaluate(() => (window as unknown as { setFocused: (value: boolean) => void }).setFocused(true));
  await expect.poll(() => snapshots).toBe(2);
  await expect.poll(() => state().then(value => value.active)).toBe(1);
});

test("two-stream HTTP1 quota leaves initial seventh tab readable and client retries only at foreground cadence", async ({ page }) => {
  // Real Chromium sockets and EventSource, not intercepted API requests. This models
  // the server's session quota; its actual enforcement is separately backend-tested.
  let active = 0; let accepted = 0; let rejected = 0; let bootstrapReads = 0; let posts = 0;
  const server = createServer(async (request, response) => {
    const path = new URL(request.url!, "http://synthetic").pathname;
    if (request.method !== "GET") { posts++; response.writeHead(405).end(); return; }
    if (path.startsWith("/api/") && request.headers.cookie !== "fixture=synthetic-session") { response.writeHead(401).end(); return; }
    if (path === "/api/v1/events") {
      if (active >= 2) { rejected++; response.writeHead(429, { "Retry-After": "15" }).end(); return; }
      active++; accepted++;
      response.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-store" });
      response.write(": connected\n\n");
      const lifetime = setTimeout(() => response.end("event: refresh.required\ndata: {}\n\n"), 15000);
      response.on("close", () => { active--; clearTimeout(lifetime); });
      return;
    }
    if (path.startsWith("/api/")) {
      if (path === "/api/v1/bootstrap") bootstrapReads++;
      const data: Record<string, unknown> = {
        "/api/v1/bootstrap": { identity: { display_name: "Fixture", assurance: "OWNER" }, household: home.household, theme: settings, layout: settings, csrf_token: "synthetic" },
        "/api/v1/home": home, "/api/v1/settings": { settings },
        "/api/v1/connection": { configured: true, connected: true, state: "ONLINE", can_connect: true, setup_required: false, household_source: "synthetic" },
      };
      response.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store" }).end(JSON.stringify(data[path] ?? { items: [], next_cursor: null }));
      return;
    }
    if (path === "/legacy") { response.writeHead(200, { "Content-Type": "text/html" }).end("<!doctype html><title>Synthetic legacy tab</title><script>window.stream = new EventSource('/api/v1/events')</script>"); return; }
    const file = path === "/" ? "index.html" : path.slice(1);
    if (!/^(index\.html|assets\/[a-zA-Z0-9_.-]+)$/.test(file)) { response.writeHead(404).end(); return; }
    try { response.writeHead(200, { "Content-Type": file.endsWith(".js") ? "text/javascript" : file.endsWith(".css") ? "text/css" : "text/html" }).end(await readFile(new URL(`../dist/${file}`, import.meta.url))); }
    catch { response.end(); }
  });
  await new Promise<void>(resolve => server.listen(0, "127.0.0.1", resolve));
  const origin = `http://127.0.0.1:${(server.address() as { port: number }).port}`;
  const legacy: Page[] = [];
  try {
    await page.context().addCookies([{ name: "fixture", value: "synthetic-session", url: origin }]);
    for (let index = 0; index < 6; index++) {
      const tab = await page.context().newPage(); legacy.push(tab); await tab.goto(`${origin}/legacy`);
    }
    await expect.poll(() => ({ active, rejected })).toEqual({ active: 2, rejected: 4 });
    await page.bringToFront();
    await page.clock.install(); await page.clock.pauseAt(new Date());
    await page.goto(origin);
    await expect(page.getByRole("heading", { name: /Welcome,/ })).toBeVisible();
    await expect.poll(() => rejected).toBe(5);
    expect(bootstrapReads).toBe(1);
    await page.clock.runFor(14000);
    expect(bootstrapReads).toBe(1); expect(rejected).toBe(5);
    await page.clock.runFor(1000);
    await expect.poll(() => bootstrapReads).toBe(2);
    await expect.poll(() => rejected).toBe(6);
    for (const tab of legacy) await tab.close();
    await expect.poll(() => active).toBe(0);
    await page.clock.runFor(15000);
    await expect.poll(() => bootstrapReads).toBe(3);
    await expect.poll(() => active).toBe(1);
    expect(accepted).toBe(3);
    await page.getByRole("button", { name: "Refresh connection status" }).click();
    await expect.poll(() => bootstrapReads).toBe(4);
    await expect.poll(() => accepted).toBe(4);
    expect(active).toBe(1); expect(posts).toBe(0);
    await expect(page.getByRole("alert")).toHaveCount(0);
  } finally {
    for (const tab of legacy) if (!tab.isClosed()) await tab.close();
    await page.goto("about:blank");
    server.closeAllConnections();
    await new Promise<void>(resolve => server.close(() => resolve()));
  }
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
