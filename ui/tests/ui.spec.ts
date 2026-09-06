import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/auth/login");
  await expect(page.getByRole("heading", { name: /Good evening/ })).toBeVisible();
});

test("desktop conversation uses the real Core cognition pipeline", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "functional acceptance runs on desktop");
  await page.getByRole("button", { name: "Anima" }).click();
  await page.getByLabel("Message Anima").fill("What is the commissioned runtime status?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("The commissioned ANIMA cognition path is connected.")).toBeVisible();
  await expect(page.getByText(/I heard you:/)).toHaveCount(0);
});

test("desktop task lifecycle is visible through the Core task path", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "functional acceptance runs on desktop");
  const title = `H4 browser task ${Date.now()}`;
  const when = new Date(Date.now() + 86_400_000).toISOString().slice(0, 16);
  await page.getByRole("button", { name: "Tasks & Calendar" }).click();
  await page.getByLabel("Reminder title").fill(title);
  await page.getByLabel("When").fill(when);
  await page.getByRole("button", { name: "Create task" }).click();
  const row = page.getByRole("listitem").filter({ hasText: title });
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Pause" }).click();
  await expect(page.getByRole("status").filter({ hasText: "SUCCEEDED" })).toBeVisible();
  await expect(row.getByText("PAUSED")).toBeVisible();
  await row.getByRole("button", { name: "Resume" }).click();
  await expect(row.getByText("ACTIVE")).toBeVisible();
  await row.getByRole("button", { name: "Cancel" }).click();
  await expect(row.getByText("CANCELLED")).toBeVisible();
});

test("desktop calendar supports edit, optimistic versioning, and cancellation", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "functional acceptance runs on desktop");
  const title = `H4 browser event ${Date.now()}`;
  const start = new Date(Date.now() + 172_800_000).toISOString().slice(0, 16);
  const end = new Date(Date.now() + 176_400_000).toISOString().slice(0, 16);
  await page.getByRole("button", { name: "Tasks & Calendar" }).click();
  await page.getByLabel("Event title").fill(title);
  await page.getByLabel("Starts").fill(start);
  await page.getByLabel("Ends").fill(end);
  await page.getByRole("button", { name: "Create event" }).click();
  const row = page.getByRole("listitem").filter({ hasText: title });
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Edit" }).click();
  const editForm = page.locator("form.edit-form");
  await expect(editForm).toBeVisible();
  await editForm.getByLabel("Title").fill(`${title} edited`);
  await editForm.getByRole("button", { name: "Save edit" }).click();
  await expect(page.getByRole("listitem").filter({ hasText: `${title} edited` })).toBeVisible();
  const editedRow = page.getByRole("listitem").filter({ hasText: `${title} edited` });
  await editedRow.getByRole("button", { name: "Cancel" }).click();
  await expect(editedRow.getByText("CANCELLED")).toBeVisible();
});

test("desktop settings apply persisted presentation preferences", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "functional acceptance runs on desktop");
  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByLabel("Appearance").selectOption("light");
  await page.getByLabel("Layout profile").selectOption("tablet");
  await page.getByLabel("Text scale").selectOption("large");
  await page.getByRole("checkbox", { name: "presence" }).uncheck();
  await page.getByRole("button", { name: "Save preferences" }).click();
  await expect(page.getByRole("status").filter({ hasText: "SUCCEEDED" })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-appearance", "light");
  await expect(page.locator("html")).toHaveAttribute("data-display-mode", "tablet");
  await page.getByRole("button", { name: "Home" }).click();
  await expect.poll(async () => page.locator(".dashboard").evaluate((node) => getComputedStyle(node).gap)).toBe("12px");
  await expect(page.locator('[data-widget="presence"]')).toHaveCount(0);
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-appearance", "light");
  await expect(page.locator("html")).toHaveAttribute("data-display-mode", "tablet");
  await expect(page.locator('[data-widget="presence"]')).toHaveCount(0);
});

test("desktop layout profiles change measured geometry and widget order", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "functional acceptance runs on desktop");
  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByLabel("Layout profile").selectOption("wall");
  const presence = page.getByRole("checkbox", { name: "presence" });
  if (!(await presence.isChecked())) await presence.check();
  await page.getByRole("button", { name: "Save preferences" }).click();
  await page.getByRole("button", { name: "Home" }).click();
  await expect.poll(async () => page.locator(".dashboard").evaluate((node) => getComputedStyle(node).gridTemplateColumns.split(" ").length)).toBe(3);
  await expect.poll(async () => page.locator(".dashboard").evaluate((node) => getComputedStyle(node).gap)).toBe("24px");
  const beforeAgendaIndex = await page.locator(".widget").evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-widget")).indexOf("agenda"));
  const wallColumns = await page.locator(".dashboard").evaluate((node) => getComputedStyle(node).gridTemplateColumns);
  await page.getByRole("button", { name: "Settings" }).click();
  const agendaUp = page.getByRole("button", { name: "Move agenda up" });
  const agendaDown = page.getByRole("button", { name: "Move agenda down" });
  if (await agendaUp.isEnabled()) await agendaUp.click();
  else await agendaDown.click();
  await page.getByRole("button", { name: "Save preferences" }).click();
  await page.getByRole("button", { name: "Home" }).click();
  await expect.poll(async () => page.locator(".widget").evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-widget")).indexOf("agenda"))).not.toBe(beforeAgendaIndex);
  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByLabel("Layout profile").selectOption("phone");
  await page.getByRole("button", { name: "Save preferences" }).click();
  await page.getByRole("button", { name: "Home" }).click();
  await expect.poll(async () => page.locator(".dashboard").evaluate((node) => getComputedStyle(node).gridTemplateColumns.split(" ").length)).toBe(1);
  expect(await page.locator(".dashboard").evaluate((node) => getComputedStyle(node).gridTemplateColumns)).not.toBe(wallColumns);
});

test("desktop home exposes governed household surfaces and truthful health", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "functional acceptance runs on desktop");
  await page.getByRole("button", { name: "Settings" }).click();
  for (const name of ["activity", "household", "reports", "health"]) {
    const widget = page.getByRole("checkbox", { name });
    if (!(await widget.isChecked())) await widget.check();
  }
  await page.getByRole("button", { name: "Save preferences" }).click();
  await page.getByRole("button", { name: "Home" }).click();
  await expect(page.getByRole("heading", { name: "Rooms & devices" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Notifications & recent actions" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "System health" })).toBeVisible();
  await expect(page.locator('[data-widget="activity"] h2')).toHaveText("Activity");
  await expect(page.getByText("Voice is planned for a later phase")).toHaveCount(0);
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByRole("checkbox", { name: "household" })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "reports" })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "health" })).toBeVisible();
});

test("desktop notification route keeps delivery destination server-owned", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "functional acceptance runs on desktop");
  await page.getByRole("button", { name: "Notifications" }).click();
  await expect(page.getByRole("heading", { name: "Notification route" })).toBeVisible();
  await page.getByLabel("Route label").fill("Overnight SenseGuard alerts");
  await page.getByLabel("Minimum alert priority").fill("80");
  await page.getByRole("button", { name: "Create route" }).click();
  await expect(page.getByRole("status").filter({ hasText: "SUCCEEDED" })).toBeVisible();
  await expect(page.getByText(/server configured/i)).toBeVisible();
  await expect(page.getByText("ntfy", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Route label")).toHaveValue("Overnight SenseGuard alerts");
});

test("responsive navigation and privacy boundary hold at each viewport", async ({ page }) => {
  await expect(page.getByRole("button", { name: "Home" })).toBeVisible();
  await page.getByRole("button", { name: "Capabilities" }).click();
  await expect(page.locator("h1", { hasText: "Capabilities" })).toBeVisible();
  await page.getByRole("button", { name: "Home" }).click();
  expect(await page.evaluate(() => Object.keys(localStorage).length)).toBe(0);
  expect(await page.evaluate(() => Object.keys(sessionStorage).length)).toBe(0);
  const storage = await page.evaluate(async () => ({
    local: Object.keys(localStorage),
    session: Object.keys(sessionStorage),
    indexed: typeof indexedDB.databases === "function" ? (await indexedDB.databases()).map((db) => db.name).filter(Boolean) : [],
    caches: "caches" in self ? await caches.keys() : [],
    workers: "serviceWorker" in navigator ? (await navigator.serviceWorker.getRegistrations()).map((registration) => registration.scope) : [],
  }));
  expect(storage.local).toEqual([]);
  expect(storage.session).toEqual([]);
  expect(storage.indexed).toEqual([]);
  expect(storage.caches).toEqual([]);
  expect(storage.workers).toEqual([]);
});

test("browser application traffic is same-origin and keyboard focus is visible", async ({ page }) => {
  const origins: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.protocol === "http:" || url.protocol === "https:") origins.push(url.origin);
  });
  await page.reload();
  await expect(page.getByRole("button", { name: "Home" })).toBeVisible();
  await page.getByRole("button", { name: "Anima" }).focus();
  await expect(page.getByRole("button", { name: "Anima" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Message Anima")).toBeVisible();
  expect(new Set(origins)).toEqual(new Set([new URL(page.url()).origin]));
});
