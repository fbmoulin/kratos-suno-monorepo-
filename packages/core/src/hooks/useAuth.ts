import { useCallback, useEffect, useState } from "react";

import type { ApiClient } from "../api";
import type { AuthStatus } from "../types";

export interface UseAuthOptions {
  /** Cliente API (web ou mobile — ambos satisfazem a interface ApiClient). */
  client: ApiClient;

  /**
   * Como redirecionar o usuário para a URL do Spotify.
   * Web:    (url) => { window.location.href = url; }
   * Mobile: (url) => WebBrowser.openAuthSessionAsync(url, redirectUri)
   *
   * A função é fire-and-forget: depois do redirect, o callback no backend
   * processa os tokens e o frontend faz refresh() quando a página volta
   * (web) ou quando o deep link dispara (mobile).
   */
  onOpenAuthUrl: (url: string) => void | Promise<void>;

  /** Se false, não faz refresh automático no mount (útil em testes). */
  autoLoad?: boolean;
}

export interface UseAuthReturn {
  auth: AuthStatus | null;
  isLoading: boolean;
  loginWithSpotify: () => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const UNAUTHENTICATED: AuthStatus = {
  authenticated: false,
  spotify_user_id: null,
  display_name: null,
  expires_at: null,
};

export function useAuth({
  client,
  onOpenAuthUrl,
  autoLoad = true,
}: UseAuthOptions): UseAuthReturn {
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const [isLoading, setIsLoading] = useState(autoLoad);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    try {
      const status = await client.getAuthStatus();
      setAuth(status);
    } catch {
      setAuth(UNAUTHENTICATED);
    } finally {
      setIsLoading(false);
    }
  }, [client]);

  useEffect(() => {
    if (autoLoad) {
      void refresh();
    }
  }, [autoLoad, refresh]);

  const loginWithSpotify = useCallback(async () => {
    const { authorize_url } = await client.initiateSpotifyLogin();
    await onOpenAuthUrl(authorize_url);
  }, [client, onOpenAuthUrl]);

  const logout = useCallback(async () => {
    await client.logout();
    await refresh();
  }, [client, refresh]);

  return { auth, isLoading, loginWithSpotify, logout, refresh };
}
