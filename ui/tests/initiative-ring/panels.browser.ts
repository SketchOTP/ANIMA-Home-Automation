import { test, expect, type Page } from "@playwright/test";

// All route responses and credentials below are declared synthetic test data.
// No request reaches Core, HA, Ring, a real household, or an owner account.
const version = "00000000-0000-4000-8000-000000000001";
const laterVersion = "00000000-0000-4000-8000-000000000002";
const config = { learning_days: 3, routine_review_days: 3, daily_review_enabled: true, routine_review_enabled: true, proactive_enabled: false, always_notify: [] as string[], device_notifications: [] as object[] };
const status = () => ({ status: "SUCCEEDED", config: structuredClone(config), config_version: null as string | null, timezone: "America/New_York", readiness: { ready: false, observed_local_days: 0, required_days: 3, first_observed_at: null as string | null, last_observed_at: null as string | null, elapsed_seconds: 0, required_elapsed_seconds: 259200, evidence_status: "SUCCEEDED", truncated: false }, proactive_eligible: false, scheduling: { status: "NOT_SCHEDULED", tasks: [] as unknown[] }, authority: "NONE", can_edit: true });
const suggestion = (id = version) => ({ suggestion_id: id, kind: "PATTERN", content: `Synthetic fixture inference ${id.slice(-1)}`, confidence: 0.4, classification: "INFERRED", review_status: "PENDING", source_refs: [{ event_id: "00000000-0000-4000-8000-000000000010", event_type: "household.ring.motion", occurred_at: "2026-09-01T10:00:00Z", recorded_at: "2026-09-01T10:05:00Z", canonical_id: "00000000-0000-4000-8000-000000000011" }], created_at: "2026-09-01T12:00:00Z", authority: "NONE" });
const ringStatus = () => ({ configured: false, connected: false, state: "WAITING_RING_SETUP", can_edit: true, can_setup: true, event_entities: 0, video_access: false, connection_basis: "HA_TRANSPORT", event_receipt_verified: false });
const form = (step: "user" | "2fa" = "user") => ({ status: "FORM", setup_id: version, step_id: step, fields: step === "user" ? [{ name: "username", type: "text", required: true }, { name: "password", type: "password", required: true }] : [{ name: "2fa", type: "password", required: true }], errors: {} });
async function initiative(page: Page, getStatus = () => status()) {
  await page.route("**/api/v1/initiative", route => route.fulfill({ json: getStatus() }));
  await page.route("**/api/v1/initiative/suggestions?**", route => route.fulfill({ json: { status: "SUCCEEDED", items: [], next_cursor: null } }));
}
async function ring(page: Page, getStatus = () => ringStatus()) {
  await page.route("**/api/v1/ring/status", route => route.fulfill({ json: getStatus() }));
  await page.route("**/api/v1/ring/setup/start", route => route.fulfill({ json: form() }));
}
async function noOverflow(page: Page) { expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true); }

test("initiative renders honest empty evidence and accessible controls without browser errors", async ({ page }, info) => {
  const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
  await initiative(page); await page.goto("/");
  await expect(page.getByRole("heading", { name: "SENTRY initiative", exact: true })).toBeVisible();
  await expect(page.getByText("Automatic wake disabled", { exact: true })).toBeVisible();
  await expect(page.getByText("Waiting for observations", { exact: true })).toBeVisible();
  await expect(page.getByText("No learned suggestions recorded.", { exact: false })).toBeVisible();
  await expect(page.getByRole("switch", { name: "Optional proactive notifications", exact: true })).not.toBeChecked();
  for (const name of ["Contact openings", "Phone connection changes", "Ring motion", "Ring doorbell"]) await expect(page.getByRole("switch", { name: `Always notify: ${name}`, exact: true })).not.toBeChecked();
  expect(await page.locator("vite-error-overlay").count()).toBe(0); await noOverflow(page); expect(errors).toEqual([]);
  await page.screenshot({ path: info.outputPath("initiative-empty.png"), fullPage: true });
});

test("initiative saves full versioned policy, reloads and validates ranges", async ({ page }) => {
  let saved = status(); const writes: unknown[] = [];
  await initiative(page, () => saved);
  await page.route("**/api/v1/initiative/configure", async route => {
    const body = route.request().postDataJSON(); writes.push(body);
    const { expected_version, ...next } = body.payload; expect(expected_version).toBe(saved.config_version);
    saved = { ...saved, config: next, config_version: version };
    await route.fulfill({ json: { status: "SUCCEEDED", result: { status: "SUCCEEDED" } } });
  });
  await page.goto("/");
  await page.getByRole("spinbutton", { name: "Learning period" }).fill("2");
  await expect(page.getByRole("button", { name: "Save initiative policy" })).toBeDisabled();
  await page.getByRole("spinbutton", { name: "Learning period" }).fill("7");
  await page.getByRole("spinbutton", { name: "Routine review interval" }).fill("14");
  await page.getByRole("switch", { name: "Always notify: Ring doorbell", exact: true }).check();
  await page.getByRole("switch", { name: "Optional proactive notifications", exact: true }).check();
  await page.getByRole("button", { name: "Save initiative policy" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Initiative settings saved" })).toBeVisible();
  expect(writes).toEqual([{ payload: { ...config, learning_days: 7, routine_review_days: 14, always_notify: ["household.ring.doorbell"], proactive_enabled: true, expected_version: null } }]);
  await page.reload(); await expect(page.getByRole("spinbutton", { name: "Learning period" })).toHaveValue("7");
  await expect(page.getByRole("switch", { name: "Always notify: Ring doorbell", exact: true })).toBeChecked();
  await expect(page.getByText("Automatic wake disabled", { exact: true })).toBeVisible();
});

test("stale inner FAILED retains draft, refreshes and blocks blind resubmit", async ({ page }) => {
  let saved = { ...status(), config_version: version }; let writes = 0;
  await initiative(page, () => saved);
  await page.route("**/api/v1/initiative/configure", async route => { writes++; saved = { ...saved, config_version: laterVersion, config: { ...config, learning_days: 5 } }; await route.fulfill({ json: { status: "SUCCEEDED", result: { status: "FAILED" } } }); });
  await page.goto("/"); await page.getByRole("spinbutton", { name: "Learning period" }).fill("8");
  await page.getByRole("button", { name: "Save initiative policy" }).click();
  await expect(page.getByText("Change not confirmed.", { exact: false })).toBeVisible();
  await expect(page.getByRole("spinbutton", { name: "Learning period" })).toHaveValue("8");
  await expect(page.getByRole("button", { name: "Save initiative policy" })).toBeDisabled();
  await page.getByRole("button", { name: "Refresh initiative", exact: true }).click();
  await expect(page.getByRole("button", { name: "Save initiative policy" })).toBeDisabled(); expect(writes).toBe(1);
  await page.getByRole("button", { name: "Discard draft and load saved settings" }).click();
  await expect(page.getByRole("spinbutton", { name: "Learning period" })).toHaveValue("5");
  await expect(page.getByRole("button", { name: "Save initiative policy" })).toBeEnabled();
});

test("suggestions paginate with original evidence and confirmation-only non-executable review", async ({ page }) => {
  await initiative(page); const one = suggestion(), two = suggestion(laterVersion); const writes: unknown[] = [];
  await page.route("**/api/v1/initiative/suggestions?**", route => route.fulfill({ json: { status: "SUCCEEDED", items: new URL(route.request().url()).searchParams.has("cursor") ? [one, two] : [one], next_cursor: new URL(route.request().url()).searchParams.has("cursor") ? null : version } }));
  await page.route("**/api/v1/initiative/review", route => { const body = route.request().postDataJSON(); writes.push(body); one.review_status = body.payload.decision; return route.fulfill({ json: { status: "SUCCEEDED" } }); });
  await page.goto("/"); await page.getByRole("button", { name: "Load more suggestions" }).click();
  await expect(page.locator(".initiative-suggestion-list > li")).toHaveCount(2);
  await page.locator(".initiative-suggestion-list > li").first().locator("summary").click();
  await expect(page.locator(".initiative-suggestion-list > li").first().getByText(one.source_refs[0].event_id, { exact: true })).toBeVisible();
  await expect(page.locator(".initiative-suggestion-list")).toContainText("Occurred"); await expect(page.locator(".initiative-suggestion-list")).toContainText("Recorded");
  await page.getByRole("button", { name: "Acknowledge suggestion" }).first().click(); expect(writes).toEqual([]);
  await expect(page.getByRole("heading", { name: "Acknowledge this inference?" })).toBeFocused();
  await page.getByRole("button", { name: "Confirm review" }).click();
  await expect(page.getByText("Suggestion review saved.", { exact: false })).toBeVisible();
  expect(writes).toEqual([{ payload: { suggestion_id: version, decision: "ACKNOWLEDGED" } }]);
  await expect(page.locator(".initiative-suggestion-list")).toContainText("acknowledged");
});

test("ready, truncated evidence and scheduling never imply running or delivered", async ({ page }) => {
  const snapshot = status(); snapshot.readiness = { ...snapshot.readiness, ready: true, observed_local_days: 4, elapsed_seconds: 259200, first_observed_at: "2026-09-01T00:00:00Z", last_observed_at: "2026-09-04T00:00:00Z", truncated: true }; snapshot.scheduling = { status: "SCHEDULED", tasks: [{}] }; snapshot.proactive_eligible = true;
  await initiative(page, () => snapshot); await page.goto("/");
  await expect(page.getByText("Learning threshold met", { exact: true })).toBeVisible();
  await expect(page.getByText("Scheduled — execution not verified", { exact: true })).toBeVisible();
  await expect(page.getByText("Evidence scan is truncated.", { exact: false })).toBeVisible();
  await expect(page.getByText("Automatic wake disabled", { exact: true })).toBeVisible();
  const before = await page.locator(".initiative-evidence").innerText();
  await page.clock.install(); await page.clock.fastForward(86_400_000);
  expect(await page.locator(".initiative-evidence").innerText()).toBe(before); await noOverflow(page);
});

test("initiative forbidden refresh clears draft and inference, malformed status fails closed", async ({ page }) => {
  await initiative(page); await page.goto("/"); await page.getByRole("spinbutton", { name: "Learning period" }).fill("9");
  await page.route("**/api/v1/initiative", route => route.fulfill({ status: 403, json: { detail: "forbidden" } }));
  await page.getByRole("button", { name: "Refresh initiative", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("no longer allowed"); await expect(page.getByRole("spinbutton")).toHaveCount(0);
  await page.route("**/api/v1/initiative", route => route.fulfill({ json: { ...status(), authority: "EXECUTE" } }));
  await page.getByRole("button", { name: "Refresh initiative", exact: true }).click();
  await expect(page.getByText("Collection and readiness are unavailable.", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save initiative policy" })).toHaveCount(0);
});

test("Ring starts only explicitly, clears secrets before network reply, completes 2FA without journals", async ({ page }, info) => {
  let current = ringStatus(); const posts: { path: string; body: unknown; csrf: string | undefined }[] = [];
  await ring(page, () => current);
  let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/api/v1/ring/setup/**", async route => {
    const request = route.request(), body = request.postDataJSON(); posts.push({ path: new URL(request.url()).pathname, body, csrf: request.headers()["x-anima-csrf"] });
    if (request.url().endsWith("start")) return route.fulfill({ json: form() });
    if (body.user_input.password) { await gate; return route.fulfill({ json: form("2fa") }); }
    current = { ...current, configured: true, connected: true, state: "CONFIGURED", can_setup: false, event_entities: 2 };
    return route.fulfill({ json: { status: "SUCCEEDED", configured: true, refresh_required: true } });
  });
  await page.goto("/?panel=ring"); await expect(page.getByText("Ring setup needed", { exact: true })).toBeVisible(); expect(posts).toEqual([]);
  await page.getByRole("button", { name: "Set up Ring", exact: true }).click();
  await page.getByLabel("Ring username", { exact: true }).fill("synthetic-ring-user"); await page.getByLabel("Ring password", { exact: true }).fill("synthetic-secret-not-real");
  await page.getByRole("button", { name: "Continue Ring sign-in" }).click();
  await expect(page.getByLabel("Ring password", { exact: true })).toHaveValue(""); await expect(page.getByLabel("Ring username", { exact: true })).toHaveValue("");
  release(); await page.getByLabel("Ring verification code", { exact: true }).fill("synthetic-code");
  await page.getByRole("button", { name: "Verify Ring code" }).click();
  await expect(page.getByText("Configured in Home Assistant", { exact: true })).toBeVisible();
  await expect(page.getByText("Connected to Home Assistant", { exact: true })).toBeVisible();
  await expect(page.getByText("Not verified", { exact: true })).toBeVisible();
  expect(posts).toEqual([
    { path: "/api/v1/ring/setup/start", body: {}, csrf: "synthetic-test-csrf" },
    { path: "/api/v1/ring/setup/continue", body: { setup_id: version, user_input: { username: "synthetic-ring-user", password: "synthetic-secret-not-real" } }, csrf: "synthetic-test-csrf" },
    { path: "/api/v1/ring/setup/continue", body: { setup_id: version, user_input: { "2fa": "synthetic-code" } }, csrf: "synthetic-test-csrf" },
  ]);
  expect(await page.evaluate(() => JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage } }))).not.toMatch(/synthetic-(secret|code|ring-user)/);
  await expect(page.locator("body")).not.toContainText("synthetic-secret-not-real"); await noOverflow(page);
  await page.screenshot({ path: info.outputPath("ring-configured-fixture.png"), fullPage: true });
});

test("Ring rejects unsupported reflected forms and non-owner setup with no secret output", async ({ page }) => {
  await ring(page); await page.route("**/api/v1/ring/setup/start", route => route.fulfill({ json: { ...form(), fields: [...form().fields, { name: "untrusted", type: "text", required: true }], description: "RAW_REFLECTION_SHOULD_NOT_RENDER" } }));
  await page.goto("/?panel=ring"); await page.getByRole("button", { name: "Set up Ring", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("not confirmed"); await expect(page.locator("input")).toHaveCount(0); await expect(page.locator("body")).not.toContainText("RAW_REFLECTION_SHOULD_NOT_RENDER");
  await page.route("**/api/v1/ring/setup/start", route => route.fulfill({ status: 403, json: { detail: "DO_NOT_RENDER_THIS_EITHER" } }));
  await page.getByRole("button", { name: "Set up Ring", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("authenticated household owner"); await expect(page.getByRole("button", { name: "Set up Ring", exact: true })).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText("DO_NOT_RENDER_THIS_EITHER");
});

test("Ring gates unavailable HA, clears expired session and never automatically posts", async ({ page }) => {
  let current = { ...ringStatus(), state: "WAITING_HA_SETUP", can_setup: false }; let posts = 0;
  page.on("request", request => { if (request.method() === "POST") posts++; });
  await ring(page, () => current); await page.goto("/?panel=ring");
  await expect(page.getByText("Home Assistant setup needed", { exact: true })).toBeVisible(); await expect(page.getByRole("button", { name: "Set up Ring", exact: true })).toHaveCount(0); expect(posts).toBe(0);
  current = ringStatus(); await page.getByRole("button", { name: "Refresh Ring status" }).click();
  await page.getByRole("button", { name: "Set up Ring", exact: true }).click();
  await page.getByLabel("Ring password", { exact: true }).fill("synthetic-draft");
  await page.route("**/api/v1/ring/status", route => route.fulfill({ status: 401, json: {} }));
  await page.getByRole("button", { name: "Refresh Ring status" }).click();
  await expect(page.getByText("Fixture session expired", { exact: true })).toBeVisible(); await expect(page.locator("input")).toHaveCount(0); expect(posts).toBe(1);
});

test("Ring provider errors are generic and secrets cleared without automatic retry", async ({ page }) => {
  await ring(page); let posts = 0;
  await page.route("**/api/v1/ring/setup/continue", route => { posts++; return route.fulfill({ status: 400, json: { detail: "synthetic-secret-do-not-reflect" } }); });
  await page.goto("/?panel=ring"); await page.getByRole("button", { name: "Set up Ring", exact: true }).click();
  await page.getByLabel("Ring username", { exact: true }).fill("synthetic-user"); await page.getByLabel("Ring password", { exact: true }).fill("synthetic-secret-do-not-reflect");
  await page.getByRole("button", { name: "Continue Ring sign-in" }).click();
  await expect(page.getByRole("alert")).toContainText("not confirmed"); await expect(page.locator("input")).toHaveCount(0); await expect(page.locator("body")).not.toContainText("synthetic-secret-do-not-reflect");
  await page.clock.install(); await page.clock.fastForward(60_000); expect(posts).toBe(1);
});

test("initiative read timeout retains draft and disables save until a successful refresh", async ({ page }) => {
  await initiative(page); await page.goto("/"); await page.getByRole("spinbutton", { name: "Learning period" }).fill("8");
  await page.clock.install();
  await page.route("**/api/v1/initiative", () => {});
  await page.getByRole("button", { name: "Refresh initiative", exact: true }).click();
  await page.clock.fastForward(10_001);
  await expect(page.getByRole("alert")).toContainText("timed out");
  await expect(page.getByRole("spinbutton", { name: "Learning period" })).toHaveValue("8");
  await expect(page.getByRole("button", { name: "Save initiative policy" })).toBeDisabled();
  await page.route("**/api/v1/initiative", route => route.fulfill({ json: status() }));
  await page.getByRole("button", { name: "Refresh initiative", exact: true }).click();
  await expect(page.getByRole("button", { name: "Save initiative policy" })).toBeEnabled();
  await expect(page.getByRole("spinbutton", { name: "Learning period" })).toHaveValue("8");
});

test("read-only initiative cannot change settings or review suggestions", async ({ page }) => {
  await initiative(page, () => ({ ...status(), can_edit: false }));
  await page.route("**/api/v1/initiative/suggestions?**", route => route.fulfill({ json: { status: "SUCCEEDED", items: [suggestion()], next_cursor: null } }));
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Save initiative policy" })).toBeDisabled();
  await expect(page.getByRole("switch", { name: "Optional proactive notifications", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Acknowledge suggestion" })).toHaveCount(0);
});

test("dismissal requires confirmation; failed review never reports success", async ({ page }) => {
  await initiative(page); let writes = 0;
  await page.route("**/api/v1/initiative/suggestions?**", route => route.fulfill({ json: { status: "SUCCEEDED", items: [suggestion()], next_cursor: null } }));
  await page.route("**/api/v1/initiative/review", route => { writes++; expect(route.request().postDataJSON()).toEqual({ payload: { suggestion_id: version, decision: "DISMISSED" } }); return route.fulfill({ json: { status: "FAILED" } }); });
  await page.goto("/"); await page.getByRole("button", { name: "Dismiss suggestion" }).click();
  await page.getByRole("button", { name: "Cancel review" }).click(); expect(writes).toBe(0);
  await page.getByRole("button", { name: "Dismiss suggestion" }).click(); await page.getByRole("button", { name: "Confirm review" }).click();
  await expect(page.getByRole("alert")).toContainText("Change not confirmed"); expect(writes).toBe(1);
  await expect(page.getByText("Suggestion review saved.", { exact: false })).toHaveCount(0);
  await expect(page.locator(".initiative-suggestion-list")).toContainText("pending");
});

test("Ring setup timeout never replays credentials or claims configured", async ({ page }) => {
  await ring(page); let writes = 0;
  await page.route("**/api/v1/ring/setup/continue", () => { writes++; });
  await page.goto("/?panel=ring"); await page.getByRole("button", { name: "Set up Ring", exact: true }).click();
  await page.getByLabel("Ring username", { exact: true }).fill("synthetic-user"); await page.getByLabel("Ring password", { exact: true }).fill("synthetic-timeout-secret");
  await page.clock.install(); await page.getByRole("button", { name: "Continue Ring sign-in" }).click();
  await page.clock.fastForward(20_001);
  await expect(page.getByRole("alert")).toContainText("not confirmed"); await expect(page.locator("input")).toHaveCount(0);
  await expect(page.getByText("Ring setup needed", { exact: true })).toBeVisible();
  await page.clock.fastForward(60_000); expect(writes).toBe(1);
});
