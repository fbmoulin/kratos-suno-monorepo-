import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderWithProviders, screen, within } from "./test/test-utils";
import App from "./App";

// Mock the API client so App renders without network calls.
vi.mock("./apiClient", () => ({
  api: {
    generateFromText: vi.fn(),
    generateFromAudio: vi.fn(),
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
});
