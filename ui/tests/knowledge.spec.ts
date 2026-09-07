import { expect, test } from "@playwright/test";

// Real isolated Core HTTP + native filesystem fixture (tests/serve_knowledge_ui.py).
// Login/policy are synthetic; no owner household, provider, or production vault.
test.beforeEach(async ({ page }) => {
  await page.goto("/auth/login");
  await expect(page.getByRole("heading", { name: /Welcome,/ })).toBeVisible();
  await page.getByRole("navigation").getByRole("button", { name: "Preferences", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Memory · Knowledge base" })).toBeVisible();
});

test("Memory real Core create read reload correct disable retract journey", async ({ page }, info) => {
  const panel = page.getByRole("region", { name: "Memory knowledge base" });
  const name = `Synthetic ${info.project.name} knowledge ${Date.now()}`;
  await panel.getByRole("button", { name: "New note", exact: true }).click();
  await panel.getByLabel("Note title", { exact: true }).fill(name);
  await panel.getByLabel("Note text", { exact: true }).fill("Synthetic observation summary, not a personal household fact.");
  await panel.getByLabel("Source ID", { exact: true }).fill("synthetic-browser-source");
  await panel.getByLabel("What this source supports", { exact: true }).fill("A deterministic validation example only.");
  await panel.getByRole("button", { name: "Save note", exact: true }).click();
  await expect(panel.getByText("Core confirmed the note change.", { exact: true })).toBeVisible();
  await expect(panel.getByRole("button", { name: `Read ${name}`, exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole("navigation").getByRole("button", { name: "Preferences", exact: true }).click();
  await panel.getByRole("button", { name: `Read ${name}`, exact: true }).click();
  await expect(panel.getByText("Synthetic observation summary, not a personal household fact.", { exact: true })).toBeVisible();
  await expect(panel.getByRole("region", { name: "Selected memory note" })).toContainText("sentry inference");
  await panel.getByRole("button", { name: "Edit note", exact: true }).click();
  await panel.getByLabel("Note text", { exact: true }).fill("Corrected synthetic observation summary.");
  await panel.getByLabel("Note enabled", { exact: true }).uncheck();
  await panel.getByRole("button", { name: "Save note correction", exact: true }).click();
  await expect(panel.getByText("Core confirmed the note change.", { exact: true })).toBeVisible();
  await panel.getByRole("button", { name: `Read ${name}`, exact: true }).click();
  await expect(panel.getByText("Corrected synthetic observation summary.", { exact: true })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("Memory-note.png"), fullPage: true });
  page.once("dialog", dialog => dialog.dismiss());
  await panel.getByRole("button", { name: "Retract note", exact: true }).click();
  await expect(panel.getByRole("button", { name: "Edit note", exact: true })).toBeVisible();
  page.once("dialog", dialog => dialog.accept());
  await panel.getByRole("button", { name: "Retract note", exact: true }).click();
  await expect(panel.getByText(/Note retracted/)).toBeVisible();
  await expect(panel.getByRole("button", { name: `Read ${name}`, exact: true })).toHaveCount(0);
  await page.screenshot({ path: info.outputPath("Memory-retracted.png"), fullPage: true });
});

test("Memory validation sends no empty or oversized write", async ({ page }) => {
  const writes: string[] = [];
  page.on("request", request => { if (request.method() === "POST" && request.url().includes("/knowledge/")) writes.push(request.url()); });
  const panel = page.getByRole("region", { name: "Memory knowledge base" });
  await panel.getByRole("button", { name: "New note", exact: true }).click();
  await panel.getByRole("button", { name: "Save note", exact: true }).click();
  expect(writes).toHaveLength(0);
  await panel.getByLabel("Note title", { exact: true }).fill("Synthetic validation only");
  await panel.getByLabel("Note text", { exact: true }).fill("é".repeat(2049));
  await panel.getByLabel("Source ID", { exact: true }).fill("synthetic-source");
  await panel.getByLabel("What this source supports", { exact: true }).fill("Synthetic test");
  await panel.getByRole("button", { name: "Save note", exact: true }).click();
  await expect(panel.getByText("Note text must be at most 4 KiB.", { exact: true })).toBeVisible();
  expect(writes).toHaveLength(0);
});

test("Memory denied write keeps draft and does not claim persistence", async ({ page }) => {
  const panel = page.getByRole("region", { name: "Memory knowledge base" });
  await page.route("**/api/v1/knowledge/create", route => route.fulfill({ json: { status: "DENIED", reason: "SYNTHETIC_DENIAL" } }));
  await panel.getByRole("button", { name: "New note", exact: true }).click();
  await panel.getByLabel("Note title", { exact: true }).fill("Synthetic denied note");
  await panel.getByLabel("Note text", { exact: true }).fill("Unpersisted synthetic draft");
  await panel.getByLabel("Source ID", { exact: true }).fill("synthetic-source");
  await panel.getByLabel("What this source supports", { exact: true }).fill("Synthetic test");
  await panel.getByRole("button", { name: "Save note", exact: true }).click();
  await expect(panel.getByText("DENIED: SYNTHETIC_DENIAL", { exact: true })).toBeVisible();
  await expect(panel.getByLabel("Note text", { exact: true })).toHaveValue("Unpersisted synthetic draft");
  await expect(panel.getByRole("button", { name: "Read Synthetic denied note", exact: true })).toHaveCount(0);
});

test("Memory unavailable is not an empty-vault claim", async ({ page }) => {
  const panel = page.getByRole("region", { name: "Memory knowledge base" });
  await page.route("**/api/v1/knowledge?**", route => route.fulfill({ status: 503, json: { detail: "KNOWLEDGE_NOT_CONFIGURED" } }));
  await panel.getByRole("button", { name: "Refresh memory", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("Memory is not configured or is unavailable");
  await expect(panel.getByRole("button", { name: "New note", exact: true })).toBeDisabled();
  await expect(panel.getByText("No curated notes yet. Nothing has been seeded.", { exact: true })).toHaveCount(0);
});

test("Memory read 401 clears all protected UI", async ({ page }) => {
  const panel = page.getByRole("region", { name: "Memory knowledge base" });
  await page.route("**/api/v1/knowledge?**", route => route.fulfill({ status: 401, json: { detail: "SESSION_EXPIRED" } }));
  await panel.getByRole("button", { name: "Refresh memory", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your home, connected", exact: true })).toBeVisible();
  await expect(panel).toHaveCount(0);
  await expect(page.getByRole("navigation")).toHaveCount(0);
});

test("Memory external edit conflict preserves the boundary and disables new writes", async ({ page }) => {
  const panel = page.getByRole("region", { name: "Memory knowledge base" });
  await page.route("**/api/v1/knowledge?**", route => route.fulfill({ status: 409, json: { detail: "KNOWLEDGE_EDIT_CONFLICT" } }));
  await panel.getByRole("button", { name: "Refresh memory", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("unreconciled external edit");
  await expect(panel.getByRole("alert")).toContainText("no automatic import");
  await expect(panel.getByRole("button", { name: "New note", exact: true })).toBeDisabled();
});

test("Long-term user-stated note keeps null retention across reload and correction", async ({ page }, info) => {
  const panel = page.getByRole("region", { name: "Memory knowledge base" });
  const name = `Synthetic durable claim ${info.project.name} ${Date.now()}`;
  await panel.getByRole("button", { name: "New note", exact: true }).click();
  await panel.getByLabel("Note title", { exact: true }).fill(name);
  await panel.getByLabel("Note text", { exact: true }).fill("Synthetic stated preference, not verified truth.");
  await expect(panel.getByLabel("Retention days (blank = no automatic expiry)", { exact: true })).toHaveValue("");
  await panel.getByRole("combobox", { name: "Knowledge basis", exact: true }).selectOption("USER_STATED");
  await panel.getByLabel("Source ID", { exact: true }).fill("synthetic-request");
  await panel.getByLabel("What this source supports", { exact: true }).fill("Attributed synthetic statement only.");
  await panel.getByRole("button", { name: "Save note", exact: true }).click();
  await expect(panel.getByText(/user-stated claim needs an attributed request/)).toBeVisible();
  await panel.getByRole("combobox", { name: "Source kind", exact: true }).selectOption("request");
  const posted = page.waitForRequest(request => request.method() === "POST" && request.url().endsWith("/knowledge/create"));
  await panel.getByRole("button", { name: "Save note", exact: true }).click();
  expect((await posted).postDataJSON().payload.retention_days).toBeNull();
  await expect(panel.getByText("Core confirmed the note change.", { exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole("navigation").getByRole("button", { name: "Preferences", exact: true }).click();
  await panel.getByRole("button", { name: `Read ${name}`, exact: true }).click();
  await expect(panel.getByText("No automatic expiry", { exact: true })).toBeVisible();
  await panel.getByRole("button", { name: "Edit note", exact: true }).click();
  await expect(panel.getByLabel("Retention days (blank = no automatic expiry)", { exact: true })).toHaveValue("");
  await panel.getByRole("combobox", { name: "Knowledge basis", exact: true }).selectOption("DISCOVERED");
  await expect(panel.getByLabel("Retention days (blank = no automatic expiry)", { exact: true })).toHaveValue("");
  await panel.getByRole("button", { name: "Save note correction", exact: true }).click();
  await expect(panel.getByText("Core confirmed the note change.", { exact: true })).toBeVisible();
});

test("Member reference and relevant search use bounded contracts", async ({ page }, info) => {
  const person = "00000000-0000-0000-0000-000000000321";
  await page.route("**/api/v1/family-routines?**", route => route.fulfill({ json: { members: [{ person_id: person, name: "Synthetic member" }] } }));
  await page.route("**/api/v1/knowledge-search?**", route => route.fulfill({ json: { status: "SUCCEEDED", items: [], truncated: false } }));
  const panel = page.getByRole("region", { name: "Memory knowledge base" });
  await panel.getByRole("button", { name: "Refresh memory", exact: true }).click();
  await expect(panel.getByLabel("Filter memory by member").getByRole("option", { name: "Synthetic member" })).toHaveCount(1);
  await panel.getByLabel("Search memory", { exact: true }).fill("garden hose");
  await panel.getByLabel("Filter memory by member").selectOption(person);
  await panel.getByLabel("Filter note type").selectOption("lesson");
  const searched = page.waitForRequest(request => request.url().includes("/knowledge-search?"));
  await panel.getByRole("button", { name: "Search notes", exact: true }).click();
  const url = new URL((await searched).url());
  expect(url.searchParams.get("person_id")).toBe(person);
  expect(url.searchParams.get("query")).toBe("garden hose");
  expect(url.searchParams.get("note_type")).toBe("lesson");
  expect(url.searchParams.get("limit")).toBe("20");
  await expect(panel.getByText("No matching notes.", { exact: true })).toBeVisible();
  await panel.getByRole("button", { name: "New note", exact: true }).click();
  await panel.getByLabel("Note title", { exact: true }).fill("Synthetic profile link");
  await panel.getByLabel("Note text", { exact: true }).fill("UI fixture only; not sent to real household.");
  await panel.getByLabel("Synthetic member", { exact: true }).check();
  await panel.getByLabel("Source ID", { exact: true }).fill("synthetic-test");
  await panel.getByLabel("What this source supports", { exact: true }).fill("UI test only.");
  await panel.getByRole("button", { name: "Add source reference" }).click();
  await panel.getByRole("combobox", { name: "Source kind", exact: true }).nth(1).selectOption("test");
  await panel.getByLabel("Source ID", { exact: true }).nth(1).fill("synthetic-test-run");
  await panel.getByLabel("What this source supports", { exact: true }).nth(1).fill("Attributed tested result only.");
  // Deliberate UI-only denied write; do not invent canonical Graph membership.
  await page.route("**/api/v1/knowledge/create", route => route.fulfill({ json: { status: "DENIED", reason: "SYNTHETIC_DENIAL" } }));
  const posted = page.waitForRequest(request => request.method() === "POST" && request.url().endsWith("/knowledge/create"));
  await panel.getByRole("button", { name: "Save note", exact: true }).click();
  const payload = (await posted).postDataJSON().payload;
  expect(payload.person_refs).toEqual([person]);
  expect(payload.source_refs[1].kind).toBe("test");
  await expect(panel.getByText("DENIED: SYNTHETIC_DENIAL", { exact: true })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("Memory-profile-editor.png"), fullPage: true });
});

test("Configured memory eligibility never claims an automatic writer is qualified", async ({ page }) => {
  const panel = page.getByRole("region", { name: "Memory knowledge base" });
  await page.route("**/api/v1/knowledge-status", route => route.fulfill({ json: { agent_memory_enabled: true, available: true, writer_status: "NOT_QUALIFIED" } }));
  await panel.getByRole("button", { name: "Refresh memory", exact: true }).click();
  await expect(panel.getByText(/eligible by configuration.*Storage available.*Automatic writer not qualified/)).toBeVisible();
  await page.route("**/api/v1/knowledge-status", route => route.fulfill({ status: 503, json: {} }));
  await panel.getByRole("button", { name: "Refresh memory", exact: true }).click();
  await expect(panel.getByText("Agent memory status unavailable; automatic capture is not established.", { exact: true })).toBeVisible();
});

test("Correcting prose does not restart an unchanged finite retention clock", async ({ page }, info) => {
  const panel = page.getByRole("region", { name: "Memory knowledge base" });
  const title = `Synthetic finite memory ${info.project.name} ${Date.now()}`;
  await panel.getByRole("button", { name: "New note", exact: true }).click();
  await panel.getByLabel("Note title", { exact: true }).fill(title);
  await panel.getByLabel("Note text", { exact: true }).fill("Original synthetic note.");
  await panel.getByLabel("Retention days (blank = no automatic expiry)", { exact: true }).fill("365");
  await panel.getByLabel("Source ID", { exact: true }).fill("synthetic-finite-source");
  await panel.getByLabel("What this source supports", { exact: true }).fill("Synthetic retention test.");
  await panel.getByRole("button", { name: "Save note", exact: true }).click();
  await expect(panel.getByText("Core confirmed the note change.", { exact: true })).toBeVisible();
  await panel.getByRole("button", { name: `Read ${title}`, exact: true }).click();
  await panel.getByRole("button", { name: "Edit note", exact: true }).click();
  await expect(panel.getByLabel("Retention days (blank = no automatic expiry)", { exact: true })).toHaveValue("365");
  await panel.getByLabel("Note text", { exact: true }).fill("Corrected synthetic note.");
  const posted = page.waitForRequest(request => request.method() === "POST" && request.url().endsWith("/knowledge/update"));
  await panel.getByRole("button", { name: "Save note correction", exact: true }).click();
  expect((await posted).postDataJSON().payload).not.toHaveProperty("retention_days");
  await expect(panel.getByText("Core confirmed the note change.", { exact: true })).toBeVisible();
});
