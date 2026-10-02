import { expect, test } from "@playwright/test";

test("supported setup and scene apply persist through actual isolated Core", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/auth/login");
  await expect(page.getByRole("heading", { name: /Welcome,/ })).toBeVisible();
  const open = (name: string) => page.getByRole("navigation").getByRole("button", { name, exact: true }).click();
  const label = `Stage6 ${info.project.name} ${Date.now()}`;
  await open("Spaces");
  await page.getByLabel("Name", { exact: true }).fill(label);
  await page.getByRole("button", { name: "Create place", exact: true }).click();
  await expect(page.getByRole("listitem").filter({ hasText: label })).toBeVisible();
  await open("Scenes");
  await page.getByLabel("Scene name", { exact: true }).fill(label);
  await page.getByRole("button", { name: "Add device state", exact: true }).click();
  await page.getByRole("button", { name: "Create scene", exact: true }).click();
  const row = page.getByRole("listitem").filter({ hasText: label });
  await expect(row).toContainText("v1");
  const attempts: Record<string, unknown>[] = [];
  page.on("request", request => {
    if (request.method() === "POST" && /\/scenes\/[^/]+\/apply$/.test(request.url())) {
      attempts.push(request.postDataJSON().payload);
    }
  });
  // Lose only the browser response AFTER actual Core has completed the call.
  // The second click must inspect the exact attempt, not dispatch a new one.
  await page.route("**/api/v1/scenes/*/apply", async route => {
    const response = await route.fetch();
    expect(response.status()).toBe(200);
    expect((await response.json()).status).toBe("SUCCEEDED");
    await route.abort("failed");
  }, { times: 1 });
  await row.getByRole("button", { name: "Apply scene", exact: true }).click();
  await expect(row.getByRole("button", { name: "Check same attempt", exact: true })).toBeVisible();
  const recovered = page.waitForResponse(response => /\/scenes\/[^/]+\/apply$/.test(response.url()) && response.status() === 200);
  await row.getByRole("button", { name: "Check same attempt", exact: true }).click();
  const outcome = await (await recovered).json();
  expect(outcome.status).toBe("SUCCEEDED");
  expect(outcome.duplicate).toBe(true);
  expect(attempts).toHaveLength(2);
  expect(attempts[1]).toEqual(attempts[0]);
  expect(outcome.result.saved_scene.version).toBe(1);
  await expect(row.getByRole("button", { name: "Apply scene", exact: true })).toBeVisible();
  await row.getByRole("button", { name: "Edit", exact: true }).click();
  await page.getByLabel("Scene name", { exact: true }).fill(`${label} revised`);
  await page.getByRole("button", { name: "Save scene", exact: true }).click();
  await expect(row).toContainText("v2");
  await row.getByRole("button", { name: "Disable", exact: true }).click();
  await expect(row.getByRole("button", { name: "Apply scene", exact: true })).toBeDisabled();
  await page.reload(); await open("Scenes");
  await expect(row).toContainText("revised");
  await expect(row).toContainText("DISABLED");
  await open("Automations");
  await page.getByLabel("Name", { exact: true }).fill(label);
  await page.getByRole("button", { name: "Create automation", exact: true }).click();
  await expect(row).toContainText("ACTIVE");
  await row.getByRole("button", { name: "Disable", exact: true }).click();
  await expect(row).toContainText("DISABLED");
  await page.reload(); await open("Automations");
  await expect(row).toContainText("DISABLED");
  await open("Alerts");
  await page.getByRole("textbox", { name: /^Event name/ }).fill(`stage6.${info.project.name}.${Date.now()}`);
  const eventName = await page.getByRole("textbox", { name: /^Event name/ }).inputValue();
  await page.getByRole("button", { name: "Create rule", exact: true }).click();
  const rule = page.getByRole("listitem").filter({ hasText: eventName });
  await expect(rule).toContainText("ACTIVE");
  await rule.getByRole("button", { name: "Disable", exact: true }).click();
  await expect(rule).toContainText("DISABLED");
  await page.reload(); await open("Alerts");
  await expect(rule).toContainText("DISABLED");
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("stage6-persisted.png"), fullPage: true });
  expect(errors).toEqual([]);
});
