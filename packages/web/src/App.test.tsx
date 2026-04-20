import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { ApiHttpError } from "@kratos-suno/core";
import { renderWithProviders, screen, userEvent, waitFor, within } from "./test/test-utils";
import App from "./App";

// Mock the API client so App renders without network calls.
// Note: `useAuth` (from @kratos-suno/core) calls `api.getAuthStatus()` on mount,
// so we stub it to an unauthenticated response.
vi.mock("./apiClient", () => ({
  api: {
    generateFromText: vi.fn(),
    generateFromAudio: vi.fn(),
    getAuthStatus: vi.fn().mockResolvedValue({
      authenticated: false,
      spotify_user_id: null,
      display_name: null,
      expires_at: null,
    }),
    initiateSpotifyLogin: vi.fn(),
    logout: vi.fn(),
    getTasteProfile: vi.fn(),
  },
}));

describe("App", () => {
  beforeEach(() => {
    // Reset URL to root before each test
    window.history.replaceState({}, "", "/");
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the app title and 4 tabs", () => {
    renderWithProviders(<App />);
    expect(
      screen.getByRole("heading", { name: /kratos suno prompt/i }),
    ).toBeInTheDocument();

    const tablist = screen.getByRole("tablist");
    const tabs = within(tablist).getAllByRole("tab");
    expect(tabs).toHaveLength(4);
    expect(tabs[0]).toHaveTextContent(/texto/i);
    expect(tabs[1]).toHaveTextContent(/áudio/i);
    expect(tabs[2]).toHaveTextContent(/spotify/i);
    expect(tabs[3]).toHaveTextContent(/salvos/i);
  });

  it("auto-switches to Spotify tab when returning from OAuth callback", () => {
    window.history.replaceState({}, "", "/?spotify=connected");
    renderWithProviders(<App />);
    const spotifyTab = screen.getByRole("tab", { name: /spotify/i });
    expect(spotifyTab).toHaveAttribute("aria-selected", "true");
  });

  it("renders the Suno 200-char footer disclaimer", () => {
    renderWithProviders(<App />);
    expect(
      screen.getByText(/respeitam o limite de 200 caracteres/i),
    ).toBeInTheDocument();
  });

  it("renders error toast with title and description when generateFromText rejects with 400", async () => {
    const user = userEvent.setup();
    const { api } = await import("./apiClient");
    (api.generateFromText as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new ApiHttpError(400, undefined, "Subject inválido", "req-test"),
    );

    renderWithProviders(<App />);

    // Fill the text input on the default (Texto) tab and submit
    const input = screen.getByPlaceholderText(/ex: coldplay/i);
    await user.type(input, "Djavan");
    const submitButton = screen.getByRole("button", { name: /gerar prompts suno/i });
    await user.click(submitButton);

    // Await the toast alert and assert its content
    const alert = await waitFor(() => screen.getByRole("alert"));
    expect(within(alert).getByText(/dados inválidos/i)).toBeInTheDocument();
    expect(within(alert).getByText(/subject inválido/i)).toBeInTheDocument();
  });
});
