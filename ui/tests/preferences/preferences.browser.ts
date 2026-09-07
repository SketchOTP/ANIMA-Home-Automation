import { test, expect, type Page } from "@playwright/test";

// Declared synthetic browser fixtures only. No real names, preferences,
// provider connections, policy decisions or durable Core writes are claimed.
const memberId = "00000000-0000-4000-8000-000000000001";
const widgets = ["status", "presence", "weather", "agenda", "tasks", "controls", "conversation", "activity", "household", "reports", "health"];
const baseSettings = { version: 1, appearance: "night", accent: "purple", density: "comfortable", reduced_motion: true, text_scale: "normal", display_mode: "desktop", visible_widgets: widgets, widget_order: widgets };
const record = (id = "00000000-0000-4000-8000-000000000010", person: string | null = null) => ({ preference_id: id, version: id,
  scope: person ? "personal" : "household", person_id: person, content: "Synthetic preference text", category: "general",
  created_at: "2026-09-07T12:00:00+00:00", provenance: { kind: "EXPLICIT_INPUT" }, status: "ACTIVE" });
async function fixture(page: Page, initial = [record()]) {
  const state = { items: initial, members: [{ person_id: memberId, name: "Synthetic member" }], can_edit: true,
    settings: { ...baseSettings }, reads: [] as URL[], writes: [] as { path: string; payload: Record<string, unknown> }[],
    failWrite: false, failRead: 0, malformed: false, hang: false, paginated: false };
  const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
  await page.route("**/api/v1/**", async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname;
    if (path === "/api/v1/events") { await route.abort(); return; }
    if (request.method() !== "GET") {
      const payload = request.postDataJSON().payload; state.writes.push({ path, payload });
      if (path === "/api/v1/settings") { state.settings = payload; await route.fulfill({ json: { settings: state.settings } }); return; }
      if (state.failWrite) { await route.fulfill({ json: { status: "FAILED", result: { status: "FAILED" } } }); return; }
      if (path.startsWith("/api/v1/preferences/")) {
        if (path.endsWith("/retract")) state.items = state.items.filter(item => item.preference_id !== payload.preference_id);
        else {
          const next = { ...record(`00000000-0000-4000-8000-${String(100 + state.writes.length).padStart(12, "0")}`, payload.person_id), content: payload.content, category: payload.category };
          state.items = [...state.items.filter(item => item.preference_id !== payload.preference_id), next];
        }
      }
      await route.fulfill({ json: { status: "SUCCEEDED", result: { status: "SUCCEEDED" } } }); return;
    }
    if (path === "/api/v1/preferences") {
      state.reads.push(url);
      if (state.hang && url.search) return;
      if (state.failRead && url.search) { await route.fulfill({ status: state.failRead, body: "PRIVATE_RAW_ERROR_MUST_NOT_RENDER" }); return; }
      if (state.malformed && url.search) { await route.fulfill({ json: { items: [null] } }); return; }
      let items = state.items.filter(item => (!url.searchParams.has("scope") || item.scope === url.searchParams.get("scope"))
        && (!url.searchParams.has("person_id") || item.person_id === url.searchParams.get("person_id"))
        && (!url.searchParams.has("category") || item.category === url.searchParams.get("category")));
      const next_cursor = state.paginated && !url.searchParams.has("cursor") && items.length > 1 ? items[0].preference_id : null;
      if (state.paginated) items = url.searchParams.has("cursor") ? items.slice(1) : items.slice(0, 1);
      await route.fulfill({ json: { items, members: state.members, can_edit: state.can_edit, next_cursor } }); return;
    }
    const home = { household: { name: "Synthetic UI fixture — not live", status: "CURRENT", summary: "Synthetic responses only" },
      security: { status: "UNKNOWN", label: "Unknown" }, presence: { people: [] }, weather: { status: "UNAVAILABLE", summary: "No observation" }, calendar: [], tasks: [], controls: [], activity: [], voice: { status: "UNAVAILABLE", label: "Unavailable" }, rooms: [], notifications: [], reports: [], recent_actions: [], pending_approvals: [], health: { status: "CURRENT", summary: "Fixture", unavailable: [], degraded: [] } };
    const data: Record<string, unknown> = {
      "/api/v1/bootstrap": { identity: { display_name: "Synthetic fixture", assurance: "OWNER" }, household: home.household, theme: state.settings, layout: state.settings, csrf_token: "synthetic-only" },
      "/api/v1/home": home, "/api/v1/settings": { settings: state.settings },
      "/api/v1/connection": { configured: false, connected: false, state: "SETUP_REQUIRED", can_connect: false },
      "/api/v1/setup/status": { available: false, state: "SETUP_REQUIRED" },
    };
    await route.fulfill({ json: data[path] ?? { items: [], next_cursor: null } });
  });
  await page.goto("/"); await expect(page.getByRole("heading", { name: /Welcome,/ })).toBeVisible();
  await page.getByRole("navigation").getByRole("button", { name: "Preferences", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Saved preferences", exact: true })).toBeVisible();
  return { state, errors };
}
const panel = (page: Page) => page.locator(".preferences-panel");
const rows = (page: Page) => panel(page).locator(".preference-cards > li");

test("synthetic shared preference is saved, reloaded, corrected to personal and explicitly retracted", async ({ page }, info) => {
  const { state, errors } = await fixture(page, []);
  const content = "Synthetic only: prefer a concise explanation.\nThis is text, not a device command.";
  await panel(page).getByRole("textbox", { name: "Preference", exact: true }).fill(content);
  await panel(page).getByRole("button", { name: "Save preference", exact: true }).click();
  await expect(rows(page)).toHaveCount(1);
  expect(state.writes[0]).toEqual({ path: "/api/v1/preferences/create", payload: { content, category: "general", person_id: null } });
  const original = state.items[0].preference_id;
  await page.reload(); await page.getByRole("navigation").getByRole("button", { name: "Preferences", exact: true }).click();
  await expect(rows(page)).toContainText(content);
  await rows(page).getByRole("button", { name: "Edit preference" }).click();
  await expect(panel(page).getByRole("heading", { name: "Correct a preference" })).toBeFocused();
  await panel(page).getByRole("combobox", { name: "Applies to", exact: true }).selectOption("personal");
  await expect(panel(page).getByRole("button", { name: "Save correction" })).toBeDisabled();
  await panel(page).getByRole("combobox", { name: "Household member", exact: true }).selectOption(memberId);
  await panel(page).getByRole("combobox", { name: "Category", exact: true }).selectOption("notifications");
  await panel(page).getByRole("button", { name: "Save correction" }).click();
  await expect(rows(page)).toContainText("Synthetic member");
  expect(state.writes[1].payload).toEqual({ preference_id: original, content, category: "notifications", person_id: memberId });
  expect(state.items[0].preference_id).not.toBe(original);
  await rows(page).getByText("Version & provenance").click();
  await expect(rows(page)).toContainText("EXPLICIT_INPUT");
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: info.outputPath("personal-preference-synthetic.png"), fullPage: true });
  await rows(page).getByRole("button", { name: "Remove preference" }).click();
  await expect(panel(page).getByRole("group", { name: "Confirm preference removal" })).toContainText("retains history");
  await panel(page).getByRole("button", { name: "Keep preference" }).click(); expect(state.writes).toHaveLength(2);
  await rows(page).getByRole("button", { name: "Remove preference" }).click();
  await panel(page).getByRole("button", { name: "Confirm removal" }).click();
  await expect(rows(page)).toHaveCount(0);
  expect(state.writes[2].payload).toEqual({ preference_id: state.writes[2].payload.preference_id });
  expect(errors).toEqual([]);
});

test("server scope member category filtering persists through pagination and reset", async ({ page }) => {
  const { state } = await fixture(page, [record(undefined, memberId), record("00000000-0000-4000-8000-000000000011", memberId), record("00000000-0000-4000-8000-000000000012")]);
  state.paginated = true;
  await panel(page).getByRole("combobox", { name: "Filter preferences", exact: true }).selectOption(memberId);
  await panel(page).getByRole("combobox", { name: "Filter category", exact: true }).selectOption("general");
  await panel(page).getByRole("button", { name: "Load more preferences" }).click();
  await expect(rows(page)).toHaveCount(2);
  const query = state.reads.filter(url => url.searchParams.has("cursor")).at(-1)!.searchParams;
  expect(Object.fromEntries(query)).toMatchObject({ scope: "personal", person_id: memberId, category: "general" });
  await panel(page).getByRole("combobox", { name: "Filter preferences", exact: true }).selectOption("household");
  await expect(rows(page)).toHaveCount(1); await expect(rows(page)).toContainText("Shared household");
  expect(state.reads.at(-1)!.searchParams.has("cursor")).toBe(false);
});

test("FAILED write preserves draft and blocks blind retry until explicit review", async ({ page }) => {
  const { state } = await fixture(page); state.failWrite = true;
  await rows(page).getByRole("button", { name: "Edit preference" }).click();
  await panel(page).getByRole("textbox", { name: "Preference", exact: true }).fill("Keep this synthetic draft");
  await panel(page).getByRole("button", { name: "Save correction" }).click();
  await expect(panel(page).getByRole("alert")).toContainText("Change not confirmed");
  await expect(panel(page).getByRole("textbox", { name: "Preference", exact: true })).toHaveValue("Keep this synthetic draft");
  await expect(panel(page).getByRole("button", { name: "Save correction" })).toBeDisabled();
  await expect(panel(page).getByRole("status")).toHaveCount(0);
  await rows(page).getByRole("button", { name: "Edit preference" }).click();
  await expect(panel(page).getByRole("button", { name: "Save correction" })).toBeEnabled();
  expect(state.writes).toHaveLength(1);
});

for (const status of [401, 403]) test(`${status} clears protected records and drafts`, async ({ page }) => {
  const { state } = await fixture(page);
  await panel(page).getByRole("textbox", { name: "Preference", exact: true }).fill("Private synthetic draft");
  state.failRead = status; await panel(page).getByRole("button", { name: "Refresh preferences" }).click();
  if (status === 401) await expect(panel(page)).toHaveCount(0);
  else { await expect(rows(page)).toHaveCount(0); await expect(panel(page).getByRole("textbox", { name: "Preference", exact: true })).toHaveValue(""); }
  await expect(page.getByText("PRIVATE_RAW_ERROR_MUST_NOT_RENDER", { exact: false })).toHaveCount(0);
});

for (const mode of ["malformed", "unavailable", "timeout"] as const) test(`${mode} read fails safely and keeps the unsaved draft`, async ({ page }) => {
  const { state, errors } = await fixture(page);
  await panel(page).getByRole("textbox", { name: "Preference", exact: true }).fill("Unsaved synthetic draft");
  if (mode === "malformed") state.malformed = true;
  if (mode === "unavailable") state.failRead = 503;
  if (mode === "timeout") { await page.clock.install(); state.hang = true; }
  await panel(page).getByRole("button", { name: "Refresh preferences" }).click();
  if (mode === "timeout") await page.clock.fastForward(10_100);
  await expect(panel(page).getByRole("button", { name: "Retry preferences", exact: true })).toBeEnabled();
  await expect(panel(page).getByRole("textbox", { name: "Preference", exact: true })).toHaveValue("Unsaved synthetic draft");
  await expect(panel(page).getByRole("button", { name: "Save preference", exact: true })).toBeDisabled();
  expect(errors).toEqual([]);
});

test("personal selection requires returned members and owner edit permission", async ({ page }) => {
  const { state } = await fixture(page, []); state.members = [];
  await panel(page).getByRole("button", { name: "Refresh preferences" }).click();
  await panel(page).getByRole("combobox", { name: "Applies to", exact: true }).selectOption("personal");
  await panel(page).getByRole("textbox", { name: "Preference", exact: true }).fill("Synthetic only");
  await expect(panel(page).getByRole("button", { name: "Save preference", exact: true })).toBeDisabled();
  await expect(panel(page).getByText("No person is assumed.", { exact: false })).toBeVisible();
  state.can_edit = false; await panel(page).getByRole("button", { name: "Refresh preferences" }).click();
  await expect(panel(page).getByRole("textbox", { name: "Preference", exact: true })).toBeDisabled();
  expect(state.writes).toHaveLength(0);
});

for (const appearance of ["night", "light", "system"] as const) test(`${appearance} theme persists purple density text display and visibility without layout overflow`, async ({ page }, info) => {
  await page.emulateMedia({ colorScheme: "light", reducedMotion: "reduce" });
  const { state, errors } = await fixture(page);
  await page.getByRole("navigation").getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("combobox", { name: "Appearance", exact: true }).selectOption(appearance);
  await page.getByRole("combobox", { name: "Accent", exact: true }).selectOption("purple");
  await page.getByRole("combobox", { name: "Density", exact: true }).selectOption("compact");
  await page.getByRole("combobox", { name: "Text scale", exact: true }).selectOption("large");
  await page.getByRole("combobox", { name: "Layout profile", exact: true }).selectOption("phone");
  await page.getByRole("button", { name: "Save preferences", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-accent", "purple");
  await expect(page.locator("html")).toHaveAttribute("data-text-scale", "large");
  expect(state.settings.visible_widgets).toEqual(widgets); expect(state.settings.reduced_motion).toBe(true);
  await page.reload(); await page.getByRole("navigation").getByRole("button", { name: "Preferences", exact: true }).click();
  const colors = await page.evaluate(() => ({ background: getComputedStyle(document.body).backgroundColor, image: getComputedStyle(document.body).backgroundImage, color: getComputedStyle(document.body).color }));
  expect(colors).toEqual(appearance === "night" ? { background: "rgb(0, 0, 0)", image: "none", color: "rgb(255, 255, 255)" } : { background: "rgb(247, 245, 250)", image: "none", color: "rgb(24, 16, 31)" });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: info.outputPath(`${appearance}-purple-synthetic.png`), fullPage: true });
  expect(errors).toEqual([]);
});

test("system dark and legacy accent choices remain usable", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await fixture(page);
  await page.getByRole("navigation").getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("combobox", { name: "Appearance", exact: true }).selectOption("system");
  for (const accent of ["ember", "sage", "sky"]) {
    await page.getByRole("combobox", { name: "Accent", exact: true }).selectOption(accent);
    await page.getByRole("button", { name: "Save preferences", exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute("data-accent", accent);
  }
  expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe("rgb(0, 0, 0)");
});
