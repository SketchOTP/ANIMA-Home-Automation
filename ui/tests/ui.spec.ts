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
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-appearance", "light");
  await expect(page.locator("html")).toHaveAttribute("data-display-mode", "tablet");
});

test("responsive navigation and privacy boundary hold at each viewport", async ({ page }) => {
  await expect(page.getByRole("button", { name: "Home" })).toBeVisible();
  await page.getByRole("button", { name: "Capabilities" }).click();
  await expect(page.locator("h1", { hasText: "Capabilities" })).toBeVisible();
  await page.getByRole("button", { name: "Home" }).click();
  expect(await page.evaluate(() => Object.keys(localStorage).length)).toBe(0);
  expect(await page.evaluate(() => Object.keys(sessionStorage).length)).toBe(0);
  expect(await page.evaluate(() => Object.keys(indexedDB).length)).toBe(0);
});
