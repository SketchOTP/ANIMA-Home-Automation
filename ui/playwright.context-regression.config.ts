import { defineConfig } from "@playwright/test";
import context from "./playwright.household-context.config";

// Adjacent visual/transport fixtures; never run mutations against owner18090.
export default defineConfig({ ...context, testMatch: "redesign.spec.ts", outputDir: "test-results-context-regression" });
