/**
 * Classifica erros do backend em mensagens PT-BR para toasts.
 * Função pura — o `action.onClick` é uma closure executada apenas no clique do usuário.
 */

import { ApiHttpError } from "@kratos-suno/core";

export interface ParsedApiError {
  title: string;
  description: string;
  status: "error" | "warning";
  action?: {
    label: string;
    onClick: () => void;
  };
}

export interface ParseApiErrorOptions {
  /** Called when the classified error needs the user to re-authenticate with Spotify. */
  onReconnectSpotify?: () => void;
}

export function parseApiError(
  err: unknown,
  opts?: ParseApiErrorOptions,
): ParsedApiError {
  if (err instanceof ApiHttpError) {
    if (err.code === "E_AUTH_MISSING") {
      return {
        title: "Sessão expirada",
        description: "Reconecte com o Spotify para continuar.",
        status: "error",
        action: opts?.onReconnectSpotify
          ? { label: "Reconectar Spotify", onClick: opts.onReconnectSpotify }
          : undefined,
      };
    }
    if (err.code === "E_TIMEOUT") {
      return {
        title: "Tempo esgotado",
        description: "A análise demorou demais. Tente novamente.",
        status: "warning",
      };
    }
    if (err.code === "E_NETWORK") {
      return {
        title: "Sem conexão",
        description: "Verifique sua internet.",
        status: "warning",
      };
    }
    if (err.code === "E_BUDGET_EXCEEDED") {
      return {
        title: "Limite diário atingido",
        description: "Esse serviço fica disponível novamente à meia-noite UTC.",
        status: "warning",
      };
    }
    if (err.status === 429) {
      const description =
        err.retryAfter !== undefined
          ? `Aguarde ${err.retryAfter}s antes de tentar novamente.`
          : "Aguarde alguns segundos antes de tentar novamente.";
      return { title: "Muitas requisições", description, status: "warning" };
    }
    if (err.status === 400) {
      return { title: "Dados inválidos", description: err.message, status: "warning" };
    }
    if (err.status === 413) {
      return {
        title: "Arquivo muito grande",
        description: "O arquivo excede 25MB.",
        status: "warning",
      };
    }
    if (err.status === 502) {
      return {
        title: "Erro na análise",
        description: "Tente novamente em alguns segundos.",
        status: "error",
      };
    }
  }

  // Fallback — unclassified. Log for production debugging.
  console.error("[parseApiError] Unclassified error", err);
  const message = err instanceof Error ? err.message : "";
  return {
    title: "Erro",
    description: message || "Erro desconhecido",
    status: "error",
  };
}
