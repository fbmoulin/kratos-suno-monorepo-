/**
 * HTTP transport — função única `request()` que todas as chamadas usam.
 * Aqui concentra: baseURL, headers comuns, timeout, error handling, session strategy.
 */

import type { ApiError } from "../types";
import type { ApiClientConfig } from "./config";
import { DEFAULT_CONFIG } from "./config";

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  body?: unknown;
  formData?: FormData;
  query?: Record<string, string | number | boolean | undefined>;
  /** Headers extras específicos desta chamada. */
  headers?: Record<string, string>;
}

export class ApiHttpError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string | undefined,
    message: string,
    public readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiHttpError";
  }
}

function buildQuery(params?: Record<string, string | number | boolean | undefined>): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) sp.append(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export async function request<T>(
  config: ApiClientConfig,
  path: string,
  opts: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, formData, query, headers: extraHeaders } = opts;
  const sessionStrategy = config.sessionStrategy ?? DEFAULT_CONFIG.sessionStrategy;
  const timeoutMs = config.timeoutMs ?? DEFAULT_CONFIG.timeoutMs;

  const url = `${config.baseURL}${path}${buildQuery(query)}`;

  // Monta headers
  const headers: Record<string, string> = { ...extraHeaders };
  if (config.sharedSecret) {
    headers["X-Kratos-Key"] = config.sharedSecret;
  }

  // Bearer token (mobile)
  if (sessionStrategy === "bearer" && config.getBearerToken) {
    const token = await Promise.resolve(config.getBearerToken());
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  // Body vs FormData
  let fetchBody: BodyInit | undefined;
  if (formData) {
    // Não setar Content-Type — fetch infere com boundary correto
    fetchBody = formData;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    fetchBody = JSON.stringify(body);
  }

  // Timeout via AbortController
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: fetchBody,
      // Só enviar credentials em browsers quando strategy === cookies
      ...(sessionStrategy === "cookies" ? { credentials: "include" as RequestCredentials } : {}),
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof Error && err.name === "AbortError") {
      throw new ApiHttpError(0, "E_TIMEOUT", `Request timeout after ${timeoutMs}ms`);
    }
    throw new ApiHttpError(0, "E_NETWORK", err instanceof Error ? err.message : "Network error");
  } finally {
    clearTimeout(timeoutId);
  }

  const requestId = res.headers.get("x-request-id") ?? undefined;

  if (!res.ok) {
    let code: string | undefined;
    let detail = `HTTP ${res.status}`;
    try {
      const json = (await res.json()) as ApiError & { code?: string };
      detail = json.detail || detail;
      code = json.code;
    } catch {
      // resposta não é JSON
    }
    throw new ApiHttpError(res.status, code, detail, requestId);
  }

  if (res.status === 204) {
    return undefined as unknown as T;
  }

  return (await res.json()) as T;
}
