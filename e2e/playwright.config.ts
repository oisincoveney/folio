import { defineConfig, devices } from "@playwright/test";

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

export default defineConfig({
  testDir: "./tests",
  /* Artifacts go into the repo-relative test-artifacts dir, keyed by ticket */
  outputDir: "../test-artifacts/INFRA-070.04",
  /* Fail fast in CI; no retries (classification is deterministic with real opencode) */
  retries: 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  /* Conservative timeout — classification via opencode can take 30-90 s */
  timeout: 180_000,
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
