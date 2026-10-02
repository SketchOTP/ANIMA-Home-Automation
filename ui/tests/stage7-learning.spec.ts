import { expect, test } from "@playwright/test";

test("automatic source forecast, honest unknown and owner correction persist", async ({ page, baseURL }, info) => {
  expect(baseURL).toBe("http://127.0.0.1:18337");
  const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
  await page.goto("/auth/login");
  await expect(page.getByRole("heading", { name: /Welcome,/ })).toBeVisible();
  const open = () => page.getByRole("navigation").getByRole("button", { name: "Preferences", exact: true }).click();
  await open();
  const panel = page.locator(".initiative-panel");
  await expect(panel.getByRole("heading", { name: "SENTRY initiative", exact: true })).toBeVisible();
  const response = await page.request.get("/api/v1/initiative"); expect(response.ok()).toBe(true);
  const before = await response.json();
  expect(before.config.proactive_enabled).toBe(false);
  const frozen = before.learning.shadow_evaluations.items[0];
  expect(frozen.commissioning.mode).toBe("AUTOMATIC_SAVED_REVIEW");
  expect(frozen.authority).toBe("NONE");
  expect(frozen.closed_opportunities).toBe(1); expect(frozen.unknown_opportunities).toBe(1);
  expect(frozen.known_opportunities).toBe(0); expect(frozen.covered_opportunities).toBe(0);
  await expect(panel.getByRole("region", { name: "Automatic forecast provenance" })).toContainText("Saved review");
  await expect(panel.getByRole("region", { name: "Automatic forecast provenance" })).toContainText("Next comparison:");
  await expect(panel.getByRole("region", { name: "Prospective shadow evaluations" })).toContainText("unknown 1");
  if (frozen.disposition !== "SUPERSEDED_HYPOTHESIS") {
    await panel.getByRole("button", { name: "Correct suggestion", exact: true }).click();
    await panel.getByRole("textbox", { name: "Owner correction", exact: true }).fill("Synthetic browser owner disputes forecast.");
    await panel.getByRole("button", { name: "Confirm review", exact: true }).click();
  }
  await expect(panel.getByRole("region", { name: "Automatic forecast provenance" })).toContainText("Stopped:");
  await page.reload(); await open();
  const after = await (await page.request.get("/api/v1/initiative")).json();
  const corrected = after.learning.shadow_evaluations.items[0];
  expect(corrected.evaluation_id).toBe(frozen.evaluation_id);
  expect(corrected.frozen_at).toBe(frozen.frozen_at);
  expect(corrected.prediction).toEqual(frozen.prediction);
  expect(corrected.windows).toEqual(frozen.windows);
  expect(corrected.disposition).toBe("SUPERSEDED_HYPOTHESIS");
  expect(after.config_version).toBe(before.config_version);
  expect(after.config.proactive_enabled).toBe(false);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await panel.screenshot({ path: info.outputPath("stage7-learning-feedback.png") });
  expect(errors).toEqual([]);
});
