import { describe, expect, it, vi } from "vitest";
import {
  renderWithProviders,
  screen,
  waitFor,
} from "../test/test-utils";
import { AudioUpload } from "./AudioUpload";

/**
 * react-dropzone uses a hidden `<input type="file">` accessed via
 * `getInputProps()`. We locate it by the container's file-input and
 * fire a `change` event with a controlled File list to exercise the
 * accept/maxSize validators.
 */
function getFileInput(): HTMLInputElement {
  const input = document
    .querySelector('input[type="file"]') as HTMLInputElement | null;
  if (!input) throw new Error("File input not found");
  return input;
}

async function dropFile(file: File) {
  const input = getFileInput();
  // jsdom doesn't implement DataTransfer. Build a FileList-shaped object
  // directly — react-dropzone reads `.length` and numeric indices
  // (plus the async `getFiles` helper which handles both shapes).
  const fileList = {
    0: file,
    length: 1,
    item: (i: number) => (i === 0 ? file : null),
    [Symbol.iterator]: function* () {
      yield file;
    },
  } as unknown as FileList;
  Object.defineProperty(input, "files", {
    value: fileList,
    configurable: true,
  });
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

describe("AudioUpload", () => {
  it("accepts a valid MP3 file and shows filename", async () => {
    renderWithProviders(
      <AudioUpload onSubmit={vi.fn()} isLoading={false} />,
    );
    const file = new File(["dummy"], "song.mp3", { type: "audio/mpeg" });
    await dropFile(file);

    await waitFor(() => {
      expect(screen.getByText(/song\.mp3/)).toBeInTheDocument();
    });
  });

  it("rejects a file with unsupported MIME and extension (e.g. text/plain .txt)", async () => {
    renderWithProviders(
      <AudioUpload onSubmit={vi.fn()} isLoading={false} />,
    );
    // Note: react-dropzone's accept check passes if EITHER the MIME
    // or the extension matches. To exercise `onDropRejected`, we need
    // a file that matches neither (e.g. a .txt text/plain file).
    const badFile = new File(["dummy"], "notes.txt", { type: "text/plain" });
    await dropFile(badFile);

    await waitFor(() => {
      expect(
        screen.getByText(/Formato não suportado/i),
      ).toBeInTheDocument();
    });
    // Filename should NOT appear in the dropzone body
    expect(screen.queryByText(/notes\.txt/)).toBeNull();
  });

  it("rejects file exceeding max size via onDropRejected", async () => {
    renderWithProviders(
      <AudioUpload onSubmit={vi.fn()} isLoading={false} />,
    );
    // 26 MB with valid MIME — dropzone's maxSize routes to onDropRejected
    const bigFile = new File(
      [new Uint8Array(26 * 1024 * 1024)],
      "big.mp3",
      { type: "audio/mpeg" },
    );
    await dropFile(bigFile);

    await waitFor(() => {
      expect(screen.getByText(/excede 25MB/i)).toBeInTheDocument();
    });
  });

  it("clears previously accepted file when a subsequent drop is rejected", async () => {
    renderWithProviders(
      <AudioUpload onSubmit={vi.fn()} isLoading={false} />,
    );

    // Step 1: drop a valid MP3, expect filename visible + submit enabled
    const goodFile = new File(["dummy"], "song.mp3", { type: "audio/mpeg" });
    await dropFile(goodFile);

    await waitFor(() => {
      expect(screen.getByText(/song\.mp3/)).toBeInTheDocument();
    });
    const submitButton = screen.getByRole("button", {
      name: /Analisar e gerar prompts/i,
    });
    expect(submitButton).not.toBeDisabled();

    // Step 2: drop an invalid .txt, expect previous filename cleared + error shown
    const badFile = new File(["dummy"], "notes.txt", { type: "text/plain" });
    await dropFile(badFile);

    await waitFor(() => {
      expect(
        screen.getByText(/Formato não suportado/i),
      ).toBeInTheDocument();
    });
    expect(screen.queryByText(/song\.mp3/)).toBeNull();
    expect(submitButton).toBeDisabled();
  });

  it("sets maxLength=200 on the user hint input", () => {
    renderWithProviders(
      <AudioUpload onSubmit={vi.fn()} isLoading={false} />,
    );
    const hint = screen.getByPlaceholderText(
      /sertanejo universitário/i,
    );
    expect(hint).toHaveAttribute("maxLength", "200");
  });
});
