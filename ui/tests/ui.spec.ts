import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/auth/login");
  await expect(page.getByRole("heading", { name: /Good evening/ })).toBeVisible();
});

test("renders the Anima household dashboard", async ({ page }) => {
  await expect(page.getByText("People at home")).toBeVisible();
  await expect(page.getByText("Coming up")).toBeVisible();
  await expect(page.getByText("Voice is planned for a later phase")).toBeVisible();
  expect(await page.evaluate(() => Object.keys(localStorage).length)).toBe(0);
  expect(await page.evaluate(() => Object.keys(sessionStorage).length)).toBe(0);
});

test("conversation remains same-origin and responds through the API", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  await page.getByRole("button", { name: "Anima" }).click();
  await page.getByLabel("Message Anima").fill("What is happening at home?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("I heard you: What is happening at home?")).toBeVisible();
  expect(requests.every((url) => url.startsWith("http://127.0.0.1:18090"))).toBe(true);
});

test("navigation works at each target viewport", async ({ page }) => {
  await page.getByRole("button", { name: "Tasks & Calendar" }).click();
  await expect(page.locator("h1", { hasText: "Tasks & Calendar" })).toBeVisible();
  await page.getByRole("button", { name: "Capabilities" }).click();
  await expect(page.locator("h1", { hasText: "Capabilities" })).toBeVisible();
});
