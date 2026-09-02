import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

test("compiled UI policy has no service worker, client database, or remote dependency", async () => {
  const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");
  assert.equal(/localStorage|indexedDB|serviceWorker|https?:\/\//i.test(source), false);
});

test("UI keeps provider traffic same-origin", async () => {
  const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");
  assert.match(source, /credentials: "same-origin"/);
  assert.doesNotMatch(source, /api\.upcitemdb|api\.bestbuy|home-assistant\.io/);
});

test("UI preserves Core semantic command and terminal-outcome contracts", async () => {
  const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");
  assert.match(source, /desired_on/);
  assert.doesNotMatch(source, /\{ state: true \}|\{ state: false \}/);
  assert.match(source, /setOutcome\(result\)/);
  assert.match(source, /widget_order/);
  assert.match(source, /display_mode/);
  assert.match(source, /appearance/);
});
