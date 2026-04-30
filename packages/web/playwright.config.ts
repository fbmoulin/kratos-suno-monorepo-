import { defineConfig } from "@playwright/test";

/**
 * Wave 2b.5 — Playwright config for the Spotify OAuth E2E.
 *
 * Runbook (local):
 *   # Terminal 1 — backend with mock mode on
 *   cd backend
 *   SPOTIFY_MOCK_MODE=true \
 *   SPOTIFY_CLIENT_ID=mock_client \
 *   SPOTIFY_REDIRECT_URI=http://localhost:8000/api/v1/auth/spotify/callback \
 *   FRONTEND_ORIGIN=http://localhost:5173 \
 *   DEBUG=true \
 *   uvicorn app.main:app --port 8000
 *
 *   # Terminal 2 — Playwright (boots Vite itself via webServer)
 *   cd packages/web
 *   pnpm test:e2e
 *
 * Env overrides:
 *   E2E_BASE_URL    — where Vite serves (default http://localhost:5173)
 *   E2E_BACKEND_URL — where FastAPI listens (default http://localhost:8000)
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  webServer: {
    command: "pnpm dev",
    url: process.env.E2E_BASE_URL || "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
