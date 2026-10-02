import { expect, test } from "@playwright/test";

test("mounted Tasks receives late live result and chat receives verified approval without replay", async ({ page, baseURL }, info) => {
  expect(baseURL).toBe("http://127.0.0.1:18338");
  const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
  await page.goto("/auth/login");
  await expect(page.getByRole("heading", { name: /Welcome,/ })).toBeVisible();
  const open = (name: string) => page.getByRole("navigation").getByRole("button", { name, exact: true }).click();
  const bootstrap = await (await page.request.get("/api/v1/bootstrap")).json();
  const headers = { "X-Anima-CSRF": bootstrap.csrf_token, Origin: baseURL! };
  const before = await (await page.request.get("/stage8-fixture-evidence")).json();
  let withheld = 0;
  let releaseLiveText = false;
  await page.route("**/api/v1/conversation/*", async route => {
    const response = await route.fetch();
    const result = await response.json();
    // Exact terminal metadata arrives before this client's live text. Delay
    // its first response only; do not submit/publish another provider result.
    if (result.status === "RESPONSE" && result.available && !releaseLiveText) {
      withheld += 1;
      await route.fulfill({ response, json: { ...result, response: null, available: false, detail: "SENTRY response is not available in the current live delivery window" } });
    } else await route.fulfill({ response });
  });
  const title = `Stage8 ${info.project.name} ${Date.now()}`;
  await open("Tasks & Calendar");
  const created = await page.request.post("/api/v1/tasks", {
    headers, data: { payload: { title, when: new Date(Date.now() + 5000).toISOString(), note: "Synthetic future result" } },
  });
  expect(created.ok()).toBe(true); expect((await created.json()).status).toBe("SUCCEEDED");
  // Existing parent invalidation refresh must reload this mounted local list.
  const row = page.getByRole("listitem").filter({ hasText: title });
  await expect(row).toBeVisible();
  await expect(row).not.toContainText("Result: RESPONSE");
  await expect(row).toContainText("Result: RESPONSE", { timeout: 15000 });
  await expect(row).toContainText("SENTRY response is not available in the current live delivery window");
  releaseLiveText = true;
  await expect(row).toContainText("Synthetic current saved task result", { timeout: 15000 });
  expect(withheld).toBeGreaterThanOrEqual(1);
  await expect(row).toContainText("not observed by task dispatch");
  const tasks = await (await page.request.get("/api/v1/tasks")).json();
  const task = tasks.items.find((item: { title: string }) => item.title === title);
  const reply = await (await page.request.get(`/api/v1/conversation/${task.latest_run.request_id}`)).json();
  expect(reply.available).toBe(true);
  expect((await page.request.get("/api/v1/conversation/00000000-0000-0000-0000-000000000001")).ok()).toBe(false);
  const scheduled = await (await page.request.get("/stage8-fixture-evidence")).json();
  expect(scheduled.plan - before.plan).toBe(1); expect(scheduled.final - before.final).toBe(1);
  // Publication evidence belongs to this exact saved task request, not a
  // previous project's delayed callback or a household-wide counter delta.
  expect(scheduled.published_by_request[task.latest_run.request_id]).toBe(1);
  expect(scheduled.physical_calls).toBe(before.physical_calls);
  await open("SENTRY");
  await page.getByLabel("Tell SENTRY what to do").fill("Synthetic ordinary delayed reply");
  await page.getByRole("button", { name: "Send to SENTRY", exact: true }).click();
  await expect(page.locator(".chat-transcript")).toContainText("SENTRY response is not available in the current live delivery window");
  await expect(page.locator(".chat-transcript")).toContainText("Synthetic current saved task result", { timeout: 15000 });
  await expect(page.getByRole("button", { name: "Send to SENTRY", exact: true })).toBeVisible();
  const chatReply = await (await page.request.get("/stage8-fixture-evidence")).json();
  expect(chatReply.plan - scheduled.plan).toBe(1); expect(chatReply.final - scheduled.final).toBe(1);
  expect(chatReply.physical_calls).toBe(scheduled.physical_calls);
  await page.getByLabel("Tell SENTRY what to do").fill("Synthetic exact approval workflow");
  const queuedResponse = page.waitForResponse(response => response.url().endsWith("/api/v1/conversation") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Send to SENTRY", exact: true }).click();
  const queued = await (await queuedResponse).json();
  await expect(page.locator(".chat-transcript")).toContainText("WAITING CONFIRMATION", { timeout: 15000 });
  const home = await (await page.request.get("/api/v1/home")).json();
  const approval = home.pending_approvals[0];
  expect(approval).toBeTruthy();
  const decision = await page.request.post(`/api/v1/approvals/${approval.approval_id}`, { headers, data: { payload: { decision: "APPROVE" } } });
  expect(decision.ok()).toBe(true);
  await expect(page.locator(".chat-transcript")).toContainText("The approved action succeeded and its result was verified.");
  const outcome = await (await page.request.get(`/api/v1/conversation/${queued.request_id}`)).json();
  expect(outcome.outcome_source).toBe("CORE_VERIFIED_ACTION_RECORD_NOT_TRANSCRIPT");
  const after = await (await page.request.get("/stage8-fixture-evidence")).json();
  expect(after.plan - chatReply.plan).toBe(1); expect(after.final - chatReply.final).toBe(1);
  expect(after.physical_calls - chatReply.physical_calls).toBe(1); expect(after.errors).toEqual([]);
  await page.screenshot({ path: info.outputPath("stage8-owner-results.png"), fullPage: true });
  expect(errors).toEqual([]);
});
