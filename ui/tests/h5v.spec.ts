import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/auth/login");
  await expect(page.getByRole("heading", { name: /Good evening/ })).toBeVisible();
});

async function requestNotification(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: "Anima" }).click();
  await page.getByLabel("Message Anima").fill("Send the deterministic H5V notification");
  await page.getByRole("button", { name: "Send" }).click();
  await page.getByRole("button", { name: "Home" }).click();
  await expect(page.getByText("Pending confirmation")).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve" }).first()).toBeVisible();
}

test("browser approval resumes the same governed episode", async ({ page }) => {
  await requestNotification(page);
  await page.getByRole("button", { name: "Approve" }).first().click();
  await expect(page.getByRole("status").filter({ hasText: "SUCCEEDED" })).toBeVisible();
  await expect(page.getByText("The notification was approved and completed.")).toBeVisible();
  await expect(page.getByText("Pending confirmation")).toHaveCount(0);
  await page.reload();
  await page.getByRole("button", { name: "Home" }).click();
  await expect(page.getByText("Pending confirmation")).toHaveCount(0);
  await expect(page.getByText("SUCCEEDED").first()).toBeVisible();
});

test("browser rejection resumes without provider dispatch", async ({ page }) => {
  await requestNotification(page);
  await page.getByRole("button", { name: "Reject" }).first().click();
  await expect(page.getByRole("status").filter({ hasText: "POLICY DENIED" })).toBeVisible();
  await expect(page.getByText("The notification was rejected and was not dispatched.")).toBeVisible();
  await expect(page.getByText("Pending confirmation")).toHaveCount(0);
});
