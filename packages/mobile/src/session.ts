/**
 * Session token management via expo-secure-store.
 *
 * O backend Kratos usa cookies HTTP-only para Spotify session no web.
 * No mobile, cookies em nativo são dolorosos (RN fetch não compartilha
 * cookies entre requests de forma confiável em iOS). Solução:
 *
 * 1. Mobile envia X-Kratos-Key (shared secret) em toda request.
 * 2. Para PKCE Spotify, mobile abre auth no browser nativo via
 *    expo-auth-session. Depois do callback, o backend precisará
 *    responder com um token ao invés de setar cookie — isso exige
 *    endpoint /api/v1/auth/spotify/mobile-callback específico.
 *
 * Este módulo só cuida do JWT que o backend eventualmente emitir
 * (Stage 3 com Clerk, ou um endpoint token-based intermediário).
 * No Stage 1 mobile, só o shared_secret é suficiente — o JWT
 * pode ser null indefinidamente.
 */

import * as SecureStore from "expo-secure-store";

const KEY = "kratos.jwt";

export async function getToken(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(KEY);
  } catch {
    return null;
  }
}

export async function setToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(KEY, token);
}

export async function clearToken(): Promise<void> {
  await SecureStore.deleteItemAsync(KEY);
}
