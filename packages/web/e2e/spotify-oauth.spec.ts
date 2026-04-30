import { expect, test } from "@playwright/test";

/**
 * Wave 2b.5 — Spotify OAuth happy path end-to-end.
 *
 * Strategy: backend runs with SPOTIFY_MOCK_MODE=true (see
 * `backend/app/services/spotify_client.py`), so token exchange and profile
 * fetches never leave the test box. The only remaining real-internet hop is
 * the browser redirect to accounts.spotify.com — we intercept that with
 * page.route() and forge a 302 straight back to the backend callback.
 *
 * Preconditions (set in the test runbook):
 *   - backend: SPOTIFY_MOCK_MODE=true, SPOTIFY_CLIENT_ID=mock_client,
 *              SPOTIFY_REDIRECT_URI=http://localhost:8000/api/v1/auth/spotify/callback
 *   - web:    VITE_API_URL=http://localhost:8000 (or default apiClient wiring)
 */

const BACKEND_URL = process.env.E2E_BACKEND_URL || "http://localhost:8000";

test("connects with Spotify and shows top artists", async ({ page }) => {
  // Intercept the Spotify consent redirect and impersonate Spotify's
  // authorization response with a 302 → backend callback.
  await page.route("**/accounts.spotify.com/authorize*", async (route) => {
    const url = new URL(route.request().url());
    const state = url.searchParams.get("state") || "mock_state";
    await route.fulfill({
      status: 302,
      headers: {
        location: `${BACKEND_URL}/api/v1/auth/spotify/callback?code=MOCK_CODE&state=${state}`,
      },
    });
  });

  // 1. Load the webapp
  await page.goto("/");

  // 2. Switch to the Spotify tab
  await page.getByRole("tab", { name: /Meu Spotify/i }).click();

  // 3. Click "Conectar com Spotify" — triggers GET /auth/spotify/login
  //    which redirects to accounts.spotify.com/authorize (intercepted above)
  await page.getByRole("button", { name: /Conectar com Spotify/i }).click();

  // 4. Backend callback redirects back to the frontend with ?spotify=connected
  await page.waitForURL(/\?spotify=connected/, { timeout: 15_000 });

  // 5. App.tsx useEffect switches to the Spotify tab (index 2) and fires a toast.
  //    Assertions: user profile and top 3 artists render.
  await expect(page.getByText("Test Artist").first()).toBeVisible({
    timeout: 10_000,
  });
  await expect(page.getByText("The Beatles")).toBeVisible();
  await expect(page.getByText("Radiohead")).toBeVisible();
  await expect(page.getByText(/Björk/i)).toBeVisible();
});
