import { defineConfig, devices } from "@playwright/test";
import os from "node:os";
import path from "node:path";

/**
 * folio Playwright config.
 *
 * baseURL is read from the environment so the same suite runs against:
 *   - port-forwarded cluster pod:  BASE_URL=http://localhost:3001  (default)
 *   - local dev:                   BASE_URL=http://localhost:3000
 *   - production (via proxy):      BASE_URL=https://folio.momokaya.ee
 *
 * Auth: folio itself has NO login screen — the Reflex app contains no auth
 * state, login components, or user model. Access is gated at the infrastructure
 * layer by an oauth2-proxy (auth.momokaya.ee OIDC). The default baseURL
 * bypasses the proxy by port-forwarding directly to the folio pod, so the
 * suite runs against the real app without needing a verify-bot session.
 */
const baseURL = process.env.BASE_URL ?? "http://localhost:3001";
const artifactRoot =
  process.env.PLAYWRIGHT_ARTIFACTS_DIR ??
  path.join(os.tmpdir(), "folio-playwright-artifacts", "INFRA-070.04");

export default defineConfig({
  testDir: "./tests",
  /* Keep artifacts outside the Reflex-watched repo tree; traces/videos trigger dev reloads. */
  outputDir: artifactRoot,
  /* Fail fast in CI; no retries (classification is deterministic with real opencode) */
  retries: 0,
  reporter: process.env.CI
    ? [["github"], ["html", { open: "never", outputFolder: path.join(artifactRoot, "html-report") }]]
    : "list",
  /* Real OpenCode path can consume parser.py's 60s classify + 2x120s extract ceiling. */
  timeout: 420_000,
  /* Default assertion timeout — generous for state updates via WebSocket */
  expect: {
    timeout: 30_000,
  },
  use: {
    baseURL,
    /* Capture a video of every test run — required by INFRA-070 #4 */
    video: "on",
    /* Always capture trace for post-mortem debugging */
    trace: "on",
    /* Reasonable viewport */
    viewport: { width: 1280, height: 800 },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
