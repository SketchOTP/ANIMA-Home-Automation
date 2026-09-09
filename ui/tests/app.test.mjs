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
  assert.match(source, /capabilities/);
  assert.match(source, /\/api\/v1\/controls\//);
  assert.match(source, /\/api\/v1\/places\/move/);
  assert.match(source, /\/api\/v1\/places\/remove/);
  assert.match(source, /parent_id/);
});

test("Spaces explains its purpose and device-assignment workflow", async () => {
  const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");
  assert.match(source, /Use Spaces to map where things are/);
  assert.match(source, /A room is a physical enclosed area/);
  assert.match(source, /A zone is a more specific or functional area/);
  assert.match(source, /assign devices to it from Devices/);
  assert.doesNotMatch(source, /A place for every device/);
});

test("Scenes explains and exposes its bounded verified preset workflow", async () => {
  const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");
  assert.match(source, /Scenes are reusable presets that set several commissioned devices together/);
  assert.match(source, /Each scene saves an On or Off choice for up to 16 power controls/);
  assert.match(source, /Saving the scene does not change any devices/);
  assert.match(source, /authorization and physical-state verification/);
  assert.match(source, /Disabling a scene prevents it from being applied but does not change any devices/);
  assert.match(source, /aria-pressed=\{scene\.enabled\}/);
  assert.match(source, /scene_id: scene\.scene_id, expected_version: scene\.version/);
  assert.doesNotMatch(source, /Set the mood with saved device states/);
});

test("owner pages explain their real workflows and boundaries", async () => {
  const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");
  const sentry = await readFile(new URL("../src/SentryChat.tsx", import.meta.url), "utf8");
  const routines = await readFile(new URL("../src/FamilyRoutines.tsx", import.meta.url), "utf8");
  const presence = await readFile(new URL("../src/HouseholdPresencePanel.tsx", import.meta.url), "utf8");
  for (const phrase of [
    "Routines records schedules and expectations you explicitly set",
    "Automations are saved rules that run without you pressing a button",
    "Alerts controls which household events deserve attention",
    "Use SENTRY to describe a household request in natural language",
    "Tasks are durable reminders or scheduled work that survive restarts",
    "Activity is a read-only view of recent household observations",
    "Users manages the people ANIMA knows about",
    "Connections shows ANIMA's registered services",
    "Backups creates server-owned snapshots",
    "Preferences stores household-wide and person-specific guidance",
    "Settings controls how the ANIMA interface looks",
  ]) assert.match(source, new RegExp(phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  for (const obsolete of [
    "When something changes, put your routine to work",
    "Choose what deserves attention",
    "Make room for what matters",
    "Make this screen feel at home",
  ]) assert.doesNotMatch(source, new RegExp(obsolete));
  assert.match(source, /source_kind !== "notification_resource"/);
  assert.match(source, /Save interface settings/);
  assert.match(source, /This page does not expose arbitrary Home Assistant services, YAML, multi-step actions, or hidden conditions/);
  assert.match(sentry, /typed ANIMA operations/);
  assert.match(sentry, /credentials and raw host access never enter the conversation/);
  assert.match(routines, /These records give SENTRY context; they do not prove presence, authenticate anyone, schedule an action, or execute an automation/);
  assert.match(routines, /Manage household users/);
  assert.doesNotMatch(routines, /Add household member|New member name|family-routines\/add-member/);
  assert.match(presence, /ANIMA keeps freshness and conflicts visible/);
  assert.match(presence, /not authentication or proof of who caused an event/);
});

test("unauthenticated UI offers the real Home Assistant sign-in route", async () => {
  const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");
  assert.match(source, /Continue with existing Home Assistant/);
  assert.match(source, /href="\/auth\/login"/);
  assert.match(source, /href="\/auth\/login\?connect=1"/);
  assert.match(source, /Credentials stay on the server/);
  assert.match(source, /AUTHENTICATION_REQUIRED/);
});

test("alert inbox exposes the existing cursor contract to owners", async () => {
  const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");
  assert.match(source, /\/api\/v1\/alerts\/events\?limit=50&cursor=/);
  assert.match(source, /Load older alerts/);
  assert.match(source, /setAlertEvents\(\(current\) => \[\.\.\.current, \.\.\.page\.items\]\)/);
});

test("SENTRY chat uses only the governed same-origin conversation boundary", async () => {
  const source = await readFile(new URL("../src/SentryChat.tsx", import.meta.url), "utf8");
  assert.match(source, /\/api\/v1\/conversation/);
  assert.match(source, /X-Anima-CSRF/);
  assert.doesNotMatch(source, /child_process|exec\(|spawn\(|ANIMA_DATABASE_URL|ANIMA_HA_ACCESS_TOKEN/);
  assert.match(source, /Live conversation text is cleared/);
  assert.match(source, /attempt < 300/);
});

test("device alert controls expose the four owner notification modes", async () => {
  const source = await readFile(new URL("../src/DeviceNotificationsPanel.tsx", import.meta.url), "utf8");
  for (const mode of ["ALWAYS", "TIME_WINDOW", "NEVER", "CONTEXTUAL"]) assert.match(source, new RegExp(mode));
  assert.match(source, /\/api\/v1\/initiative\/configure/);
  for (const event of ["UNLOCKED", "LOCKED", "OPENED", "CLOSED", "MOTION", "DOORBELL"]) assert.match(source, new RegExp(event));
  assert.match(source, /Other signals continue to use the household default/);
});

test("Users exposes persistent access, Wi-Fi, and private face enrollment controls", async () => {
  const source = await readFile(new URL("../src/UsersPanel.tsx", import.meta.url), "utf8");
  assert.match(source, /Register face profile/);
  assert.match(source, /Improve face profile/);
  assert.match(source, /Remove this capture/);
  assert.match(source, /SENTRY access/);
  assert.match(source, /Associated Wi-Fi MAC addresses/);
  assert.match(source, /Captured pictures stay in temporary memory only/);
});
