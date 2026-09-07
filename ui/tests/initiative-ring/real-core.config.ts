import { defineConfig } from "@playwright/test";
import existing from "../../playwright.household-context.config";

// Lead starts the isolated PG/OPA fixture at 18293. This config starts nothing.
export default defineConfig({ ...existing, testDir: "..", testMatch: "initiative.spec.ts", outputDir: "/tmp/anima-initiative-real-core-results" });
