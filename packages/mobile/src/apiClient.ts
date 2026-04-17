/**
 * Cliente API singleton para o app mobile.
 *
 * Diferença em relação ao web:
 * - sessionStrategy: "bearer" (RN não tem cookies confiáveis)
 * - getBearerToken lê de SecureStore (pode ser null no Stage 1)
 * - sharedSecret vem de EXPO_PUBLIC_SHARED_SECRET
 */

import { createApiClient } from "@kratos-suno/core";

import { getToken } from "./session";

const API_BASE = process.env.EXPO_PUBLIC_API_BASE;
const SHARED_SECRET = process.env.EXPO_PUBLIC_SHARED_SECRET;

if (!API_BASE) {
  console.warn(
    "[kratos-suno] EXPO_PUBLIC_API_BASE não configurado. " +
      "Copie .env.example para .env e defina a URL do backend.",
  );
}

export const api = createApiClient({
  baseURL: API_BASE ?? "",
  sharedSecret: SHARED_SECRET,
  sessionStrategy: "bearer",
  getBearerToken: getToken,
  timeoutMs: 60_000, // áudio pode demorar em conexão mobile
});
