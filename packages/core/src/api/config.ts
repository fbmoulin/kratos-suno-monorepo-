/**
 * API client configuration — platform-agnostic.
 *
 * Cada plataforma (web, mobile) passa sua config ao criar o client.
 * Isso permite:
 *  - web: credentials:"include" (cookies HTTP-only)
 *  - mobile: header Authorization com token vindo de expo-secure-store
 *  - ambos: mesma assinatura das funções, mesmos types
 */

export interface ApiClientConfig {
  /** URL base do backend. Ex: "https://api.kratos-suno.com" ou "" (dev com proxy). */
  baseURL: string;

  /** Shared secret do Stage 1 — opcional, só se o backend exigir X-Kratos-Key. */
  sharedSecret?: string;

  /**
   * Estratégia de sessão.
   * - "cookies": browser, envia credentials:"include" (web)
   * - "bearer":  mobile/desktop, envia Authorization: Bearer <token>
   */
  sessionStrategy?: "cookies" | "bearer";

  /**
   * Getter do token bearer (mobile). Chamado a cada request.
   * Deve retornar null se ainda não autenticado.
   */
  getBearerToken?: () => string | null | Promise<string | null>;

  /** Timeout em ms. Default 30s. */
  timeoutMs?: number;
}

export const DEFAULT_CONFIG: Required<Pick<ApiClientConfig, "sessionStrategy" | "timeoutMs">> = {
  sessionStrategy: "cookies",
  timeoutMs: 30_000,
};
