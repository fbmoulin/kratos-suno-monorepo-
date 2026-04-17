/**
 * Client API singleton do web. Usa cookies para sessão (Spotify PKCE)
 * e o shared secret do Stage 1 via env var.
 */

import { createApiClient } from "@kratos-suno/core";

export const api = createApiClient({
  baseURL: import.meta.env.VITE_API_BASE || "",
  sharedSecret: import.meta.env.VITE_SHARED_SECRET || undefined,
  sessionStrategy: "cookies",
  timeoutMs: 60_000, // áudio pode demorar
});
