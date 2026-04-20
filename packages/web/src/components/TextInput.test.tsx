import { describe, expect, it, vi } from "vitest";
import {
  renderWithProviders,
  screen,
  userEvent,
} from "../test/test-utils";
import { TextInput } from "./TextInput";

describe("TextInput", () => {
  it("renders counter showing 0/200 initially", () => {
    renderWithProviders(<TextInput onSubmit={vi.fn()} isLoading={false} />);
    const counter = screen.getByTestId("subject-char-counter");
    expect(counter).toHaveTextContent("0/200");
  });

  it("counter updates as user types", async () => {
    const user = userEvent.setup();
    renderWithProviders(<TextInput onSubmit={vi.fn()} isLoading={false} />);
    const input = screen.getByPlaceholderText(
      "Ex: Coldplay, Bohemian Rhapsody, Djavan",
    );
    await user.type(input, "hello");
    expect(screen.getByTestId("subject-char-counter")).toHaveTextContent(
      "5/200",
    );
  });

  it("counter marks warning state when over 180 characters", async () => {
    const user = userEvent.setup();
    renderWithProviders(<TextInput onSubmit={vi.fn()} isLoading={false} />);
    const input = screen.getByPlaceholderText(
      "Ex: Coldplay, Bohemian Rhapsody, Djavan",
    );
    // Paste 181 chars — above WARNING_THRESHOLD (180)
    await user.click(input);
    await user.paste("a".repeat(181));
    const counter = screen.getByTestId("subject-char-counter");
    expect(counter).toHaveTextContent("181/200");
    expect(counter).toHaveAttribute("data-warning", "true");
  });

  it("sets maxLength=200 on the input element", () => {
    renderWithProviders(<TextInput onSubmit={vi.fn()} isLoading={false} />);
    const input = screen.getByPlaceholderText(
      "Ex: Coldplay, Bohemian Rhapsody, Djavan",
    );
    expect(input).toHaveAttribute("maxLength", "200");
  });
});
