import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen, userEvent } from "../test/test-utils";
import { ErrorBoundary } from "./ErrorBoundary";
import { useState } from "react";

function Bomb({ shouldExplode }: { shouldExplode: boolean }) {
  if (shouldExplode) {
    throw new Error("Test explosion");
  }
  return <div>Safe content</div>;
}

describe("ErrorBoundary", () => {
  it("renders children when no error is thrown", () => {
    renderWithProviders(
      <ErrorBoundary>
        <Bomb shouldExplode={false} />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Safe content")).toBeInTheDocument();
  });

  it("renders fallback UI when child throws", () => {
    // Suppress expected error log from React
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    renderWithProviders(
      <ErrorBoundary>
        <Bomb shouldExplode />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Algo deu errado")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /tentar novamente/i }),
    ).toBeInTheDocument();
    spy.mockRestore();
  });

  it("invokes onError callback when child throws", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const onError = vi.fn();
    renderWithProviders(
      <ErrorBoundary onError={onError}>
        <Bomb shouldExplode />
      </ErrorBoundary>,
    );
    expect(onError).toHaveBeenCalledOnce();
    expect(onError.mock.calls[0][0]).toBeInstanceOf(Error);
    spy.mockRestore();
  });

  it("keeps showing fallback when retrying without changing the failing cause", async () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const user = userEvent.setup();

    function Controlled() {
      return (
        <ErrorBoundary>
          <Bomb shouldExplode />
        </ErrorBoundary>
      );
    }

    renderWithProviders(<Controlled />);
    expect(screen.getByText("Algo deu errado")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: /tentar novamente/i }),
    );

    expect(screen.getByText("Algo deu errado")).toBeInTheDocument();

    spy.mockRestore();
  });

  it("recovers when the failing cause is removed before reset", async () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const user = userEvent.setup();

    function Recoverable() {
      const [shouldExplode, setShouldExplode] = useState(true);

      return (
        <ErrorBoundary
          fallback={(_error, reset) => (
            <button
              onClick={() => {
                setShouldExplode(false);
                reset();
              }}
            >
              Recover
            </button>
          )}
        >
          <Bomb shouldExplode={shouldExplode} />
        </ErrorBoundary>
      );
    }

    renderWithProviders(<Recoverable />);
    await user.click(screen.getByRole("button", { name: "Recover" }));

    expect(screen.getByText("Safe content")).toBeInTheDocument();
    spy.mockRestore();
  });

  it("uses custom fallback when provided", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    renderWithProviders(
      <ErrorBoundary
        fallback={(error, reset) => (
          <div>
            <span>Custom: {error.message}</span>
            <button onClick={reset}>Custom Reset</button>
          </div>
        )}
      >
        <Bomb shouldExplode />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Custom: Test explosion")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Custom Reset" }),
    ).toBeInTheDocument();
    spy.mockRestore();
  });
});
