import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { ApiHttpError } from "@kratos-suno/core";
import { parseApiError } from "./parseApiError";

describe("parseApiError", () => {
  let errorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // Silence console.error in tests that intentionally trigger the fallback.
    errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    errorSpy.mockRestore();
  });

  it("maps E_AUTH_MISSING to session-expired error without action when no callback provided", () => {
    const err = new ApiHttpError(401, "E_AUTH_MISSING", "Auth missing", "req-1");
    const parsed = parseApiError(err);
    expect(parsed.title).toBe("Sessão expirada");
    expect(parsed.description).toBe("Reconecte com o Spotify para continuar.");
    expect(parsed.status).toBe("error");
    expect(parsed.action).toBeUndefined();
  });

  it("maps E_AUTH_MISSING to session-expired error with reconnect action when callback provided", () => {
    const onReconnectSpotify = vi.fn();
    const err = new ApiHttpError(401, "E_AUTH_MISSING", "Auth missing", "req-1");
    const parsed = parseApiError(err, { onReconnectSpotify });
    expect(parsed.title).toBe("Sessão expirada");
    expect(parsed.description).toBe("Reconecte com o Spotify para continuar.");
    expect(parsed.status).toBe("error");
    expect(parsed.action).toBeDefined();
    expect(parsed.action?.label).toBe("Reconectar Spotify");
    expect(typeof parsed.action?.onClick).toBe("function");
  });

  it("invokes onReconnectSpotify when action.onClick is called for E_AUTH_MISSING", () => {
    const onReconnectSpotify = vi.fn();
    const err = new ApiHttpError(401, "E_AUTH_MISSING", "Auth missing", "req-1");
    const parsed = parseApiError(err, { onReconnectSpotify });
    expect(onReconnectSpotify).not.toHaveBeenCalled();
    parsed.action?.onClick();
    expect(onReconnectSpotify).toHaveBeenCalledTimes(1);
  });

  it("maps status 429 with retryAfter to rate-limit warning including seconds", () => {
    const err = new ApiHttpError(429, "E_RATE_LIMIT", "Max 10 requests/hour", "req-2", 42);
    const parsed = parseApiError(err);
    expect(parsed.title).toBe("Muitas requisições");
    expect(parsed.description).toBe("Aguarde 42s antes de tentar novamente.");
    expect(parsed.status).toBe("warning");
  });

  it("maps status 429 without retryAfter to generic rate-limit warning", () => {
    const err = new ApiHttpError(429, "E_RATE_LIMIT", "Max 10 requests/hour", "req-2b");
    const parsed = parseApiError(err);
    expect(parsed.title).toBe("Muitas requisições");
    expect(parsed.description).toBe("Aguarde alguns segundos antes de tentar novamente.");
    expect(parsed.status).toBe("warning");
  });

  it("maps E_BUDGET_EXCEEDED to daily-limit warning", () => {
    const err = new ApiHttpError(402, "E_BUDGET_EXCEEDED", "Budget exceeded", "req-3");
    const parsed = parseApiError(err);
    expect(parsed.title).toBe("Limite diário atingido");
    expect(parsed.description).toBe(
      "Esse serviço fica disponível novamente à meia-noite UTC.",
    );
    expect(parsed.status).toBe("warning");
  });

  it("maps status 400 to invalid-data warning with err.message", () => {
    const err = new ApiHttpError(400, undefined, "subject must be at least 2 chars", "req-4");
    const parsed = parseApiError(err);
    expect(parsed.title).toBe("Dados inválidos");
    expect(parsed.description).toBe("subject must be at least 2 chars");
    expect(parsed.status).toBe("warning");
  });

  it("maps status 413 to file-too-large warning", () => {
    const err = new ApiHttpError(413, undefined, "Payload too large", "req-5");
    const parsed = parseApiError(err);
    expect(parsed.title).toBe("Arquivo muito grande");
    expect(parsed.description).toBe("O arquivo excede 25MB.");
    expect(parsed.status).toBe("warning");
  });

  it("maps status 502 to upstream-error", () => {
    const err = new ApiHttpError(502, undefined, "Bad gateway", "req-6");
    const parsed = parseApiError(err);
    expect(parsed.title).toBe("Erro na análise");
    expect(parsed.description).toBe("Tente novamente em alguns segundos.");
    expect(parsed.status).toBe("error");
  });

  it("maps E_TIMEOUT code to timeout warning", () => {
    const err = new ApiHttpError(0, "E_TIMEOUT", "Request timeout after 60000ms");
    const parsed = parseApiError(err);
    expect(parsed.title).toBe("Tempo esgotado");
    expect(parsed.description).toBe("A análise demorou demais. Tente novamente.");
    expect(parsed.status).toBe("warning");
  });

  it("maps E_NETWORK code to network warning", () => {
    const err = new ApiHttpError(0, "E_NETWORK", "fetch failed");
    const parsed = parseApiError(err);
    expect(parsed.title).toBe("Sem conexão");
    expect(parsed.description).toBe("Verifique sua internet.");
    expect(parsed.status).toBe("warning");
  });

  it("falls back to generic error for unknown errors and logs to console.error", () => {
    const err = new Error("Something weird");
    const parsed = parseApiError(err);
    expect(parsed.title).toBe("Erro");
    expect(parsed.description).toBe("Something weird");
    expect(parsed.status).toBe("error");
    expect(errorSpy).toHaveBeenCalledWith(
      "[parseApiError] Unclassified error",
      err,
    );
  });

  it("falls back to 'Erro desconhecido' when err has no message", () => {
    const parsed = parseApiError(null);
    expect(parsed.title).toBe("Erro");
    expect(parsed.description).toBe("Erro desconhecido");
    expect(parsed.status).toBe("error");
    expect(errorSpy).toHaveBeenCalledWith(
      "[parseApiError] Unclassified error",
      null,
    );
  });
});
