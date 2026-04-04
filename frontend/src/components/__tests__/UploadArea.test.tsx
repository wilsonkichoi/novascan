/**
 * UploadArea tests (frontend/src/components/UploadArea.tsx)
 *
 * Tests the upload area contract from SPEC.md Milestone 2:
 * - Accepts JPEG and PNG files
 * - Rejects non-JPEG/PNG file types (client-side validation)
 * - Rejects files exceeding 10 MB (client-side validation)
 * - Limits uploads to 10 files per batch
 * - Provides camera capture input (mobile) and file picker
 * - Supports drag-and-drop
 * - Shows validation error messages for rejected files
 * - Disabled state prevents interaction
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import UploadArea from "@/components/UploadArea";

function createFile(
  name: string,
  sizeBytes: number,
  type: string,
): File {
  const buffer = new ArrayBuffer(sizeBytes);
  return new File([buffer], name, { type });
}

/**
 * Helper to get the multiple file input from the rendered container.
 * The component has two hidden file inputs: one for camera (with capture attr)
 * and one for file picker (with multiple attr).
 */
function getMultipleFileInput(container: HTMLElement): HTMLInputElement {
  const inputs = container.querySelectorAll('input[type="file"]');
  const input = Array.from(inputs).find((el) => el.hasAttribute("multiple"));
  if (!input) throw new Error("Could not find multiple file input");
  return input as HTMLInputElement;
}

/**
 * Simulate file selection via fireEvent.change.
 * We use fireEvent instead of userEvent.upload because userEvent respects
 * the HTML accept attribute and silently drops non-matching files, which
 * prevents us from testing the component's JavaScript validation.
 */
function simulateFileChange(input: HTMLInputElement, files: File[]): void {
  // Create a minimal FileList-like structure
  const fileList = {
    length: files.length,
    item: (i: number) => files[i] ?? null,
    [Symbol.iterator]: function* () {
      for (const f of files) yield f;
    },
  };
  for (let i = 0; i < files.length; i++) {
    (fileList as Record<number, File>)[i] = files[i];
  }

  fireEvent.change(input, { target: { files: fileList } });
}

describe("UploadArea", () => {
  let onFilesSelected: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onFilesSelected = vi.fn();
  });

  // ---- Rendering ----

  it("renders drag-and-drop zone with instructions", () => {
    render(<UploadArea onFilesSelected={onFilesSelected} />);

    expect(
      screen.getByText(/drag and drop receipt images here/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/JPEG or PNG/i)).toBeInTheDocument();
    expect(screen.getByText(/10 MB/i)).toBeInTheDocument();
  });

  it("renders a Choose Files button", () => {
    render(<UploadArea onFilesSelected={onFilesSelected} />);

    expect(
      screen.getByRole("button", { name: /choose files/i }),
    ).toBeInTheDocument();
  });

  it("renders a camera capture button for mobile", () => {
    render(<UploadArea onFilesSelected={onFilesSelected} />);

    expect(
      screen.getByRole("button", { name: /take photo/i }),
    ).toBeInTheDocument();
  });

  it("renders a hidden file input with accept=image/jpeg,image/png and multiple", () => {
    const { container } = render(
      <UploadArea onFilesSelected={onFilesSelected} />,
    );

    const fileInputs = container.querySelectorAll('input[type="file"]');
    // Should have at least one file input that accepts JPEG/PNG
    const multipleInput = Array.from(fileInputs).find(
      (input) => input.hasAttribute("multiple"),
    );
    expect(multipleInput).toBeDefined();
    expect(multipleInput).toHaveAttribute("accept", "image/jpeg,image/png");
  });

  it("renders a hidden camera input with capture=environment", () => {
    const { container } = render(
      <UploadArea onFilesSelected={onFilesSelected} />,
    );

    const fileInputs = container.querySelectorAll('input[type="file"]');
    const cameraInput = Array.from(fileInputs).find(
      (input) => input.hasAttribute("capture"),
    );
    expect(cameraInput).toBeDefined();
    expect(cameraInput).toHaveAttribute("capture", "environment");
  });

  // ---- Accepts valid JPEG files ----

  it("accepts a valid JPEG file", () => {
    const { container } = render(
      <UploadArea onFilesSelected={onFilesSelected} />,
    );

    const file = createFile("receipt.jpg", 2 * 1024 * 1024, "image/jpeg");
    simulateFileChange(getMultipleFileInput(container), [file]);

    expect(onFilesSelected).toHaveBeenCalledWith([file]);
  });

  it("accepts a valid PNG file", () => {
    const { container } = render(
      <UploadArea onFilesSelected={onFilesSelected} />,
    );

    const file = createFile("receipt.png", 5 * 1024 * 1024, "image/png");
    simulateFileChange(getMultipleFileInput(container), [file]);

    expect(onFilesSelected).toHaveBeenCalledWith([file]);
  });

  it("accepts multiple valid files at once", () => {
    const { container } = render(
      <UploadArea onFilesSelected={onFilesSelected} />,
    );

    const files = [
      createFile("a.jpg", 1024, "image/jpeg"),
      createFile("b.png", 2048, "image/png"),
      createFile("c.jpg", 4096, "image/jpeg"),
    ];
    simulateFileChange(getMultipleFileInput(container), files);

    expect(onFilesSelected).toHaveBeenCalledWith(files);
  });

  // ---- Rejects invalid file types ----
  // NOTE: We use fireEvent.change (via simulateFileChange) for type rejection
  // tests because userEvent.upload respects the HTML accept attribute and
  // silently drops non-matching files. We want to test the component's
  // JavaScript validation, not the browser's native filtering.

  it("rejects a PDF file and shows an error message", () => {
    const { container } = render(
      <UploadArea onFilesSelected={onFilesSelected} />,
    );

    const file = createFile("document.pdf", 1024, "application/pdf");
    simulateFileChange(getMultipleFileInput(container), [file]);

    expect(onFilesSelected).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/not a JPEG or PNG/i)).toBeInTheDocument();
  });

  it("rejects a GIF file", () => {
    const { container } = render(
      <UploadArea onFilesSelected={onFilesSelected} />,
    );

    const file = createFile("animation.gif", 1024, "image/gif");
    simulateFileChange(getMultipleFileInput(container), [file]);

    expect(onFilesSelected).not.toHaveBeenCalled();
    expect(screen.getByText(/not a JPEG or PNG/i)).toBeInTheDocument();
  });

  it("rejects a WebP file", () => {
    const { container } = render(
      <UploadArea onFilesSelected={onFilesSelected} />,
    );

    const file = createFile("photo.webp", 1024, "image/webp");
    simulateFileChange(getMultipleFileInput(container), [file]);

    expect(onFilesSelected).not.toHaveBeenCalled();
    expect(screen.getByText(/not a JPEG or PNG/i)).toBeInTheDocument();
  });

  // ---- Rejects files exceeding 10 MB ----

  it("rejects a file larger than 10 MB and shows size error", () => {
    const { container } = render(
      <UploadArea onFilesSelected={onFilesSelected} />,
    );

    const file = createFile("huge.jpg", 11 * 1024 * 1024, "image/jpeg");
    simulateFileChange(getMultipleFileInput(container), [file]);

    expect(onFilesSelected).not.toHaveBeenCalled();
    expect(screen.getByText(/10 MB size limit/i)).toBeInTheDocument();
  });

  it("accepts a file at exactly 10 MB", () => {
    const { container } = render(
      <UploadArea onFilesSelected={onFilesSelected} />,
    );

    const file = createFile("exact.jpg", 10 * 1024 * 1024, "image/jpeg");
    simulateFileChange(getMultipleFileInput(container), [file]);

    expect(onFilesSelected).toHaveBeenCalledWith([file]);
  });

  it("rejects a file at 10 MB + 1 byte", () => {
    const { container } = render(
      <UploadArea onFilesSelected={onFilesSelected} />,
    );

    const file = createFile("over.jpg", 10 * 1024 * 1024 + 1, "image/jpeg");
    simulateFileChange(getMultipleFileInput(container), [file]);

    expect(onFilesSelected).not.toHaveBeenCalled();
    expect(screen.getByText(/10 MB size limit/i)).toBeInTheDocument();
  });

  // ---- Limits to max files ----

  it("rejects when selecting more files than the limit (default 10)", () => {
    const { container } = render(
      <UploadArea onFilesSelected={onFilesSelected} />,
    );

    const files = Array.from({ length: 11 }, (_, i) =>
      createFile(`receipt${i}.jpg`, 1024, "image/jpeg"),
    );
    simulateFileChange(getMultipleFileInput(container), files);

    expect(onFilesSelected).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("accepts exactly 10 files (the default limit)", () => {
    const { container } = render(
      <UploadArea onFilesSelected={onFilesSelected} />,
    );

    const files = Array.from({ length: 10 }, (_, i) =>
      createFile(`receipt${i}.jpg`, 1024, "image/jpeg"),
    );
    simulateFileChange(getMultipleFileInput(container), files);

    expect(onFilesSelected).toHaveBeenCalledWith(files);
  });

  it("respects custom maxFiles prop", () => {
    const { container } = render(
      <UploadArea onFilesSelected={onFilesSelected} maxFiles={3} />,
    );

    const files = Array.from({ length: 4 }, (_, i) =>
      createFile(`receipt${i}.jpg`, 1024, "image/jpeg"),
    );
    simulateFileChange(getMultipleFileInput(container), files);

    expect(onFilesSelected).not.toHaveBeenCalled();
  });

  it("accounts for currentFileCount when enforcing the limit", () => {
    const { container } = render(
      <UploadArea
        onFilesSelected={onFilesSelected}
        maxFiles={10}
        currentFileCount={8}
      />,
    );

    // Already have 8 files, trying to add 3 more exceeds limit of 10
    const files = Array.from({ length: 3 }, (_, i) =>
      createFile(`receipt${i}.jpg`, 1024, "image/jpeg"),
    );
    simulateFileChange(getMultipleFileInput(container), files);

    expect(onFilesSelected).not.toHaveBeenCalled();
  });

  it("allows files when currentFileCount + new files equals maxFiles", () => {
    const { container } = render(
      <UploadArea
        onFilesSelected={onFilesSelected}
        maxFiles={10}
        currentFileCount={8}
      />,
    );

    // 8 existing + 2 new = 10 total, should be allowed
    const files = [
      createFile("a.jpg", 1024, "image/jpeg"),
      createFile("b.jpg", 1024, "image/jpeg"),
    ];
    simulateFileChange(getMultipleFileInput(container), files);

    expect(onFilesSelected).toHaveBeenCalledWith(files);
  });

  // ---- Mixed valid and invalid files ----

  it("passes only valid files from a mixed batch", () => {
    const { container } = render(
      <UploadArea onFilesSelected={onFilesSelected} />,
    );

    const validFile = createFile("good.jpg", 1024, "image/jpeg");
    const invalidType = createFile("bad.pdf", 1024, "application/pdf");
    const tooLarge = createFile("big.jpg", 11 * 1024 * 1024, "image/jpeg");

    simulateFileChange(getMultipleFileInput(container), [validFile, invalidType, tooLarge]);

    expect(onFilesSelected).toHaveBeenCalledWith([validFile]);
    // Should show errors for the invalid files
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  // ---- Drag and drop ----

  it("accepts files via drag and drop", () => {
    render(<UploadArea onFilesSelected={onFilesSelected} />);

    const dropZone = screen.getByText(/drag and drop/i).closest("div")!;
    const file = createFile("dropped.jpg", 1024, "image/jpeg");

    const dataTransfer = {
      files: [file],
      items: [{ kind: "file", type: "image/jpeg", getAsFile: () => file }],
      types: ["Files"],
    };

    fireEvent.dragOver(dropZone, { dataTransfer });
    fireEvent.drop(dropZone, { dataTransfer });

    expect(onFilesSelected).toHaveBeenCalledWith([file]);
  });

  it("validates files from drag and drop the same as file input", () => {
    render(<UploadArea onFilesSelected={onFilesSelected} />);

    const dropZone = screen.getByText(/drag and drop/i).closest("div")!;
    const file = createFile("bad.gif", 1024, "image/gif");

    const dataTransfer = {
      files: [file],
      items: [{ kind: "file", type: "image/gif", getAsFile: () => file }],
      types: ["Files"],
    };

    fireEvent.drop(dropZone, { dataTransfer });

    expect(onFilesSelected).not.toHaveBeenCalled();
    expect(screen.getByText(/not a JPEG or PNG/i)).toBeInTheDocument();
  });

  // ---- Disabled state ----

  it("does not process files when disabled", async () => {
    const { container } = render(
      <UploadArea onFilesSelected={onFilesSelected} disabled />,
    );

    const file = createFile("receipt.jpg", 1024, "image/jpeg");
    const multipleInput = Array.from(
      container.querySelectorAll('input[type="file"]'),
    ).find((input) => input.hasAttribute("multiple")) as HTMLInputElement;

    // Disabled inputs won't fire change events via userEvent.upload,
    // so check that the input is actually disabled
    expect(multipleInput).toBeDisabled();
  });

  it("disables the Choose Files button when disabled", () => {
    render(<UploadArea onFilesSelected={onFilesSelected} disabled />);

    expect(
      screen.getByRole("button", { name: /choose files/i }),
    ).toBeDisabled();
  });

  it("disables the Take Photo button when disabled", () => {
    render(<UploadArea onFilesSelected={onFilesSelected} disabled />);

    expect(
      screen.getByRole("button", { name: /take photo/i }),
    ).toBeDisabled();
  });

  // ---- Empty file list ----

  it("does nothing when no files are selected (empty FileList)", async () => {
    const { container } = render(
      <UploadArea onFilesSelected={onFilesSelected} />,
    );

    const multipleInput = Array.from(
      container.querySelectorAll('input[type="file"]'),
    ).find((input) => input.hasAttribute("multiple")) as HTMLInputElement;

    // Simulate empty change event
    fireEvent.change(multipleInput, { target: { files: [] } });

    expect(onFilesSelected).not.toHaveBeenCalled();
  });

  // ---- Max files display ----

  it("displays the max files count in the instructions", () => {
    render(
      <UploadArea onFilesSelected={onFilesSelected} maxFiles={5} />,
    );

    expect(screen.getByText(/max 5 files/i)).toBeInTheDocument();
  });
});
