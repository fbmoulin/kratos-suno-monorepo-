import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "../test/test-utils";
import { AudioLoadingStatus } from "./AudioLoadingStatus";

describe("AudioLoadingStatus", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders nothing when isLoading=false", () => {
    renderWithProviders(<AudioLoadingStatus isLoading={false} />);
    expect(screen.queryByText(/Extraindo áudio/i)).toBeNull();
    expect(
      screen.queryByText(/Isso pode levar 30-40 segundos/i),
    ).toBeNull();
  });

  it("renders upfront banner + initial status + 0s timer when isLoading=true", () => {
    vi.useFakeTimers();
    renderWithProviders(<AudioLoadingStatus isLoading />);
    expect(
      screen.getByText("Isso pode levar 30-40 segundos"),
    ).toBeInTheDocument();
    expect(screen.getByText("Extraindo áudio...")).toBeInTheDocument();
    expect(screen.getByText("⏱ 0s")).toBeInTheDocument();
  });

  it("timer increments every second and message rotates after 5s", () => {
    vi.useFakeTimers();
    renderWithProviders(<AudioLoadingStatus isLoading />);

    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(screen.getByText("Analisando estilo...")).toBeInTheDocument();
    expect(screen.getByText("⏱ 5s")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(screen.getByText("Gerando prompts...")).toBeInTheDocument();
    expect(screen.getByText("⏱ 10s")).toBeInTheDocument();
  });

  it("clears interval + resets elapsed when isLoading flips false then true", () => {
    vi.useFakeTimers();
    const { rerender } = renderWithProviders(<AudioLoadingStatus isLoading />);

    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(screen.getByText("⏱ 3s")).toBeInTheDocument();

    rerender(<AudioLoadingStatus isLoading={false} />);
    expect(screen.queryByText(/Extraindo áudio/i)).toBeNull();

    // Advance more — should not throw, nothing to update
    act(() => {
      vi.advanceTimersByTime(5000);
    });

    rerender(<AudioLoadingStatus isLoading />);
    expect(screen.getByText("⏱ 0s")).toBeInTheDocument();
    expect(screen.getByText("Extraindo áudio...")).toBeInTheDocument();
  });
});
