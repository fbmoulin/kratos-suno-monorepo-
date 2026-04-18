/**
 * Deep link helpers for the Spotify mobile OAuth flow (W1-B).
 *
 * The backend's /api/v1/auth/spotify/mobile-callback redirects to
 *   kratossuno://spotify-connected?token=<jwt>
 * (or ?error=<code> on failure). This module parses the URL and stores
 * the JWT in expo-secure-store so ``apiClient`` can pick it up as a
 * Bearer token on subsequent requests.
 */

import * as Linking from "expo-linking";

import { setToken } from "./session";

export interface SpotifyConnectedParams {
  token?: string;
  error?: string;
}

/** Parse a ``kratossuno://spotify-connected?token=...`` URL into typed params. */
export function parseSpotifyConnectedUrl(url: string): SpotifyConnectedParams {
  const parsed = Linking.parse(url);
  const qp = parsed.queryParams ?? {};
  const token = qp.token;
  const error = qp.error;
  return {
    token: typeof token === "string" ? token : undefined,
    error: typeof error === "string" ? error : undefined,
  };
}

/**
 * Capture the JWT from a deep link and persist it.
 *
 * Returns an object describing whether the capture succeeded so the caller
 * can decide whether to navigate to the success screen or surface the error.
 */
export async function handleSpotifyConnectedUrl(
  url: string,
): Promise<{ ok: boolean; error?: string }> {
  const { token, error } = parseSpotifyConnectedUrl(url);
  if (error) return { ok: false, error };
  if (!token) return { ok: false, error: "no_token" };
  await setToken(token);
  return { ok: true };
}
