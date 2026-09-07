import { expect, test, type Page } from "@playwright/test";

test("owner creates, reloads, versions, disables, enables and retracts a persisted routine", async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/auth/login");
  await expect(page.getByRole("heading", { name: /Welcome,/ })).toBeVisible();
  const open = () => page.getByRole("navigation").getByRole("button", { name: "Routines", exact: true }).click();
  await open();
  await expect(page.getByRole("combobox", { name: /^Household member/ })).toBeEnabled();
  await expect(page.getByLabel("Routine label")).toHaveValue("");
  await expect(page.getByLabel("Start time")).toHaveValue("");
  await expect(page.getByLabel("End time")).toHaveValue("");
  const label = `Synthetic browser expectation ${testInfo.project.name} ${Date.now()}`;
  await page.getByRole("combobox", { name: /^Household member/ }).selectOption({ label: "Synthetic member" });
  await page.getByLabel("Routine label").fill(label);
  await page.getByRole("checkbox", { name: "Mon", exact: true }).check();
  await page.getByRole("checkbox", { name: "Wed", exact: true }).check();
  await page.getByLabel("Start time").fill("22:30");
  await page.getByLabel("End time").fill("06:45");
  await page.getByLabel("IANA time zone").fill("America/New_York");
  await page.getByLabel("Room or zone (optional)").selectOption({ label: "Synthetic room" });
  await page.getByLabel("Description", { exact: true }).fill("Synthetic test only; not a real person's schedule.");
  await page.getByRole("button", { name: "Save routine", exact: true }).click();
  const row = () => page.getByRole("listitem").filter({ hasText: label });
  await expect(row()).toContainText("Synthetic member · Enabled");
  await expect(row()).toContainText("(+1 day)");
  const before = await page.request.get("/api/v1/family-routines?limit=100");
  const original = (await before.json()).items.find((item: { label: string }) => item.label === label);
  expect(original.provenance.kind).toBe("EXPLICIT_INPUT");
  expect(original.authority).toBe("NONE");
  await page.reload(); await open();
  await expect(row()).toContainText("Synthetic room");
  await page.getByRole("button", { name: `Edit ${label}`, exact: true }).click();
  await expect(page.getByLabel("Start time")).toHaveValue("22:30");
  await page.getByLabel("Description", { exact: true }).fill("Synthetic revised description");
  await page.getByRole("button", { name: "Save routine changes" }).click();
  await expect(row()).toContainText("Synthetic revised description");
  await page.getByRole("button", { name: `Disable ${label}`, exact: true }).click();
  await expect(row()).toContainText("Synthetic member · Disabled");
  await page.reload(); await open();
  await expect(row()).toContainText("Disabled");
  const after = await page.request.get("/api/v1/family-routines?limit=100");
  const latest = (await after.json()).items.find((item: { label: string }) => item.label === label);
  expect(latest.routine_id).not.toBe(original.routine_id);
  expect(latest.enabled).toBe(false);
  await row().getByText("Version & provenance").click();
  await expect(row()).toContainText("OWNER_DECLARED_EXPECTATION");
  await row().getByRole("button", { name: `Enable ${label}`, exact: true }).click();
  await expect(row()).toContainText("Synthetic member · Enabled");
  await page.reload(); await open();
  await expect(row()).toContainText("Synthetic member · Enabled");
  await row().getByRole("button", { name: `Remove ${label}`, exact: true }).click();
  const confirmation = page.getByRole("group", { name: "Confirm routine removal" });
  await expect(confirmation).toContainText("not permanent deletion");
  await confirmation.getByRole("button", { name: "Keep routine" }).click();
  await expect(row()).toBeVisible();
  await row().getByRole("button", { name: `Remove ${label}`, exact: true }).click();
  await confirmation.getByRole("button", { name: "Confirm removal" }).click();
  await expect(row()).toHaveCount(0);
  await expect(page.getByRole("status").filter({ hasText: "Routine removed from the active list. History retained." })).toBeVisible();
  await page.reload(); await open();
  await expect(row()).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("routine-retracted-persisted.png"), fullPage: true });
  await page.getByRole("navigation").getByRole("button", { name: "Anima", exact: true }).click();
  await expect(page.getByRole("heading", { name: "SENTRY voice control" })).toBeVisible();
  await expect(page.locator(".conversation textarea, .conversation input")).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("voice-only.png"), fullPage: true });
  expect(errors).toEqual([]);
});

test("owner adds a canonical member then selects the reloaded option without granting authority", async ({ page }, testInfo) => {
  await openRoutines(page);
  await page.getByText("Add household member", { exact: true }).click();
  await expect(page.getByText("This does not create a login, grant permissions, or establish observed presence.", { exact: false })).toBeVisible();
  const name = `Synthetic added member ${testInfo.project.name} ${Date.now()}`;
  await page.getByLabel("New member name").fill(name);
  const request = page.waitForRequest(request => request.url().endsWith("/family-routines/add-member"));
  await page.getByRole("button", { name: "Add member", exact: true }).click();
  expect((await request).postDataJSON()).toEqual({ payload: { name } });
  await expect(page.getByRole("status").filter({ hasText: "Household member added." })).toBeVisible();
  await page.reload(); await openRoutines(page, false);
  const members = page.getByRole("combobox", { name: /^Household member/ });
  await expect(members.locator("option").filter({ hasText: name })).toHaveCount(1);
  await members.selectOption({ label: name });
  expect(await members.inputValue()).not.toBe("");
});

// All cases below explicitly mock routine responses. They qualify UI boundaries,
// not production data, OPA decisions, or live persistence.
const memberA = "00000000-0000-4000-8000-000000000001";
const memberB = "00000000-0000-4000-8000-000000000002";
const mockRoutine = (id = "00000000-0000-4000-8000-000000000010", person = memberA) => ({
  routine_id: id, version: id, person_id: person, person_name: "Mock member A",
  label: "Mock expectation", days: [0, 2], start: "22:30", end: "06:45", timezone: "America/New_York",
  place_id: null, place_name: null, notes: "Synthetic only", enabled: true,
  created_at: "2026-09-07T12:00:00+00:00", provenance: { kind: "EXPLICIT_INPUT" },
  classification: "OWNER_DECLARED_EXPECTATION", authority: "NONE",
});
const mockPage = (items = [mockRoutine()], next_cursor: string | null = null) => ({
  items, next_cursor, members: [{ person_id: memberA, name: "Mock member A" }, { person_id: memberB, name: "Mock member B" }], places: [], can_edit: true,
});
async function openRoutines(page: Page, login = true) {
  if (login) { await page.goto("/auth/login"); await expect(page.getByRole("heading", { name: /Welcome,/ })).toBeVisible(); }
  await page.getByRole("navigation").getByRole("button", { name: "Routines", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Saved family routines" })).toBeVisible();
}

test("mock day presets remain editable and invalid empty or equal-time windows never submit", async ({ page }) => {
  await page.route("**/api/v1/family-routines?*", route => route.fulfill({ json: mockPage() }));
  let writes = 0;
  await page.route("**/api/v1/family-routines/create", route => { writes++; return route.fulfill({ json: { status: "FAILED" } }); });
  await openRoutines(page);
  await page.getByRole("button", { name: "Edit Mock expectation", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Edit family routine" })).toBeFocused();
  for (const [preset, checked] of [["Weekdays", 5], ["Weekends", 2], ["Every day", 7]] as const) {
    await page.getByRole("button", { name: preset, exact: true }).click();
    await expect(page.getByRole("group", { name: "Days — local start day" }).locator("input:checked")).toHaveCount(checked);
  }
  await page.getByRole("checkbox", { name: "Sun", exact: true }).uncheck();
  await expect(page.getByRole("group", { name: "Days — local start day" }).locator("input:checked")).toHaveCount(6);
  await page.getByRole("button", { name: "Cancel edit" }).click();
  await page.getByRole("combobox", { name: /^Household member/ }).selectOption(memberA);
  await page.getByLabel("Routine label").fill("Mock unsaved");
  await page.getByLabel("Start time").fill("08:00"); await page.getByLabel("End time").fill("08:00");
  await page.getByRole("button", { name: "Save routine", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Select at least one day" })).toBeVisible();
  expect(writes).toBe(0);
});

test("mock member filtering is server scoped and remains on each pagination request", async ({ page }) => {
  const queries: URLSearchParams[] = [];
  await page.route("**/api/v1/family-routines?*", route => {
    const query = new URL(route.request().url()).searchParams; queries.push(query);
    if (!query.get("person_id")) return route.fulfill({ json: mockPage() });
    if (query.get("person_id") === memberB) return route.fulfill({ json: mockPage([]) });
    const second = { ...mockRoutine("00000000-0000-4000-8000-000000000011"), label: "Mock second page" };
    return route.fulfill({ json: query.has("cursor") ? mockPage([second]) : mockPage([mockRoutine()], mockRoutine().routine_id) });
  });
  await openRoutines(page);
  const filter = page.getByRole("combobox", { name: "Filter routines by member" });
  await filter.selectOption(memberA);
  await page.getByRole("button", { name: "Load more routines" }).click();
  await expect(page.getByRole("button", { name: "Edit Mock second page", exact: true })).toBeVisible();
  expect(queries.at(-1)?.get("person_id")).toBe(memberA);
  expect(queries.at(-1)?.get("cursor")).toBe(mockRoutine().routine_id);
  await filter.selectOption(memberB);
  await expect(page.getByText("No routines saved for this member.", { exact: true })).toBeVisible();
  expect(queries.at(-1)?.has("cursor")).toBe(false);
  await expect(page.getByRole("button", { name: "Edit Mock expectation", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Load more routines" })).toHaveCount(0);
});

test("mock stale FAILED update refreshes versions but keeps draft and does not retry", async ({ page }) => {
  let failed = false, writes = 0, reads = 0;
  await page.route("**/api/v1/family-routines?*", route => { reads++; return route.fulfill({ json: mockPage([failed ? mockRoutine("00000000-0000-4000-8000-000000000012") : mockRoutine()]) }); });
  await page.route("**/api/v1/family-routines/update", route => { failed = true; writes++; return route.fulfill({ json: { status: "FAILED", detail: "Routine version changed; reload before editing" } }); });
  await openRoutines(page);
  await page.getByRole("button", { name: "Edit Mock expectation", exact: true }).click();
  await page.getByLabel("Description", { exact: true }).fill("Keep my mock draft");
  const initialReads = reads;
  await page.getByRole("button", { name: "Save routine changes" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Change not confirmed" })).toBeVisible();
  expect(reads).toBeGreaterThan(initialReads);
  await expect(page.getByLabel("Description", { exact: true })).toHaveValue("Keep my mock draft");
  await expect(page.getByRole("button", { name: "Save routine changes" })).toBeDisabled();
  await expect(page.getByRole("status").filter({ hasText: "Routine updated" })).toHaveCount(0);
  await page.getByRole("button", { name: "Edit Mock expectation", exact: true }).click();
  await expect(page.getByRole("button", { name: "Save routine changes" })).toBeEnabled();
  await expect(page.getByLabel("Description", { exact: true })).toHaveValue("Synthetic only");
  expect(writes).toBe(1);
});

test("mock rejected member filter can reset without trapping retry or losing the draft", async ({ page }) => {
  await page.route("**/api/v1/family-routines?*", route => route.fulfill(new URL(route.request().url()).searchParams.has("person_id")
    ? { status: 400, json: { detail: "Member is no longer available" } }
    : { json: mockPage() }));
  await openRoutines(page);
  await page.getByLabel("Routine label").fill("Preserve mock draft");
  await page.getByRole("combobox", { name: "Filter routines by member" }).selectOption(memberA);
  await page.getByRole("button", { name: "Reset member filter" }).click();
  await expect(page.getByRole("combobox", { name: "Filter routines by member" })).toHaveValue("");
  await expect(page.getByRole("combobox", { name: /^Household member/ })).toBeEnabled();
  await expect(page.getByLabel("Routine label")).toHaveValue("Preserve mock draft");
});

test("mock 403 refresh clears records, member options and protected drafts", async ({ page }) => {
  let denied = false;
  await page.route("**/api/v1/family-routines?*", route => route.fulfill(denied ? { status: 403, json: { detail: "DO_NOT_DISPLAY_RAW" } } : { json: mockPage() }));
  await openRoutines(page);
  await page.getByRole("button", { name: "Edit Mock expectation", exact: true }).click();
  denied = true;
  await page.getByRole("button", { name: "Refresh routines" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "no longer have access" })).toBeVisible();
  await expect(page.getByLabel("Routine label")).toHaveValue("");
  await expect(page.getByRole("combobox", { name: /^Household member/ })).toBeDisabled();
  await expect(page.getByText("Mock expectation", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Remove Mock expectation", exact: true })).toHaveCount(0);
  await expect(page.getByText("DO_NOT_DISPLAY_RAW", { exact: false })).toHaveCount(0);
});

for (const failure of ["bad shape", "invalid weekday", "503", "invalid JSON"] as const) {
  test(`mock ${failure} read fails safely, keeps unsaved draft and permits explicit reload`, async ({ page }) => {
    const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
    let broken = false;
    await page.route("**/api/v1/family-routines?*", route => {
      if (!broken) return route.fulfill({ json: mockPage() });
      if (failure === "503") return route.fulfill({ status: 503, body: "DO_NOT_DISPLAY_RAW" });
      if (failure === "invalid JSON") return route.fulfill({ contentType: "application/json", body: "DO_NOT_DISPLAY_RAW" });
      return route.fulfill({ json: failure === "bad shape" ? { items: null } : mockPage([{ ...mockRoutine(), days: [99] }]) });
    });
    await openRoutines(page);
    await page.getByLabel("Routine label").fill("Unsaved mock draft");
    broken = true; await page.getByRole("button", { name: "Refresh routines" }).click();
    await expect(page.getByRole("button", { name: "Retry routines", exact: true })).toBeEnabled();
    await expect(page.getByLabel("Routine label")).toHaveValue("Unsaved mock draft");
    await expect(page.getByRole("button", { name: "Save routine", exact: true })).toBeDisabled();
    await expect(page.getByText("DO_NOT_DISPLAY_RAW", { exact: false })).toHaveCount(0);
    broken = false; await page.getByRole("button", { name: "Retry routines", exact: true }).click();
    await expect(page.getByRole("combobox", { name: /^Household member/ })).toBeEnabled();
    await expect(page.getByLabel("Routine label")).toHaveValue("Unsaved mock draft");
    expect(errors).toEqual([]);
  });
}

test("mock hung load times out with an actionable retry", async ({ page }) => {
  await page.clock.install();
  await page.route("**/api/v1/family-routines?*", () => { /* Deliberately leave this synthetic read pending. */ });
  await openRoutines(page);
  await expect(page.getByRole("button", { name: "Loading routines…", exact: true })).toBeVisible();
  await page.clock.fastForward(10_100);
  await expect(page.getByRole("alert").filter({ hasText: "timed out" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry routines", exact: true })).toBeEnabled();
});

test("mock no-member setup exposes add form while read-only members cannot mutate", async ({ page }) => {
  let readonly = false;
  await page.route("**/api/v1/family-routines?*", route => route.fulfill({ json: readonly ? { ...mockPage(), can_edit: false } : { ...mockPage([]), members: [] } }));
  await openRoutines(page);
  await expect(page.getByRole("combobox", { name: /^Household member/ })).toBeDisabled();
  await page.getByText("Add household member", { exact: true }).click();
  await expect(page.getByLabel("New member name")).toBeEnabled();
  readonly = true; await page.getByRole("button", { name: "Refresh routines" }).click();
  await expect(page.getByText("Only the authenticated household owner can change routines.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit Mock expectation", exact: true })).toHaveCount(0);
  await expect(page.getByText("Add household member", { exact: true })).toHaveCount(0);
});

test("routine session expiry clears protected forms and records", async ({ page }) => {
  await page.goto("/auth/login");
  await expect(page.getByRole("heading", { name: /Welcome,/ })).toBeVisible();
  await page.getByRole("navigation").getByRole("button", { name: "Routines", exact: true }).click();
  await expect(page.getByRole("combobox", { name: /^Household member/ })).toBeEnabled();
  await page.route("**/api/v1/family-routines?*", route => route.fulfill({ status: 401, json: { detail: "AUTHENTICATION_REQUIRED" } }));
  await page.getByRole("button", { name: "Refresh routines" }).click();
  await expect(page.getByRole("heading", { name: "Your home, connected" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: /^Household member/ })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Saved family routines" })).toHaveCount(0);
});
