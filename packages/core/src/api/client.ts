/**
 * API client factory.
 *
 * Uso no web:
 *   const api = createApiClient({ baseURL: "", sessionStrategy: "cookies", sharedSecret: import.meta.env.VITE_SHARED_SECRET });
 *
 * Uso no mobile:
 *   const api = createApiClient({
 *     baseURL: "https://api.kratos-suno.com",
 *     sessionStrategy: "bearer",
 *     getBearerToken: () => SecureStore.getItemAsync("jwt"),
 *     sharedSecret: Constants.expoConfig.extra.SHARED_SECRET,
 *   });
 *
 * Depois: `await api.generateFromText({ subject: "Coldplay" })`.
 */

import type {
  AuthStatus,
  GenerateResponse,
  GenerateTextRequest,
  SavedPrompt,
  SavedPromptCreate,
  SavedPromptList,
  SpotifyAuthURL,
  SpotifyTimeRange,
  TasteProfile,
} from "../types";
import type { ApiClientConfig } from "./config";
import { request } from "./http";

export interface ApiClient {
  // Generation
  generateFromText(req: GenerateTextRequest): Promise<GenerateResponse>;
  generateFromAudio(
    file: File | Blob,
    userHint?: string,
    artistToAvoid?: string,
  ): Promise<GenerateResponse>;

  // Auth (Spotify PKCE)
  getAuthStatus(): Promise<AuthStatus>;
  /**
   * W1-B: ``platform`` hints the backend whether to use the web callback
   * (cookie-based) or the mobile callback (JWT + deep link).
   */
  initiateSpotifyLogin(platform?: "web" | "mobile"): Promise<SpotifyAuthURL>;
  logout(): Promise<void>;

  // Spotify
  getTasteProfile(timeRange?: SpotifyTimeRange): Promise<TasteProfile>;

  // Saved prompts
  listSavedPrompts(): Promise<SavedPromptList>;
  createSavedPrompt(payload: SavedPromptCreate): Promise<SavedPrompt>;
  deleteSavedPrompt(id: number): Promise<void>;
}

export function createApiClient(config: ApiClientConfig): ApiClient {
  return {
    generateFromText: (req) =>
      request<GenerateResponse>(config, "/api/v1/generate/text", {
        method: "POST",
        body: req,
      }),

    generateFromAudio: (file, userHint, artistToAvoid) => {
      const fd = new FormData();
      fd.append("file", file as Blob);
      if (userHint) fd.append("user_hint", userHint);
      if (artistToAvoid) fd.append("artist_to_avoid", artistToAvoid);
      fd.append("variants_to_generate", "3");
      return request<GenerateResponse>(config, "/api/v1/generate/audio", {
        method: "POST",
        formData: fd,
      });
    },

    getAuthStatus: () => request<AuthStatus>(config, "/api/v1/auth/status"),

    initiateSpotifyLogin: (platform = "web") =>
      request<SpotifyAuthURL>(config, "/api/v1/auth/spotify/login", {
        query: { platform },
      }),

    logout: () => request<void>(config, "/api/v1/auth/logout", { method: "POST" }),

    getTasteProfile: (timeRange = "medium_term") =>
      request<TasteProfile>(config, "/api/v1/spotify/profile", {
        query: { time_range: timeRange },
      }),

    listSavedPrompts: () =>
      request<SavedPromptList>(config, "/api/v1/prompts"),

    createSavedPrompt: (payload) =>
      request<SavedPrompt>(config, "/api/v1/prompts", {
        method: "POST",
        body: payload,
      }),

    deleteSavedPrompt: (id) =>
      request<void>(config, `/api/v1/prompts/${id}`, { method: "DELETE" }),
  };
}
