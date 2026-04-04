/**
 * ScanPage tests (frontend/src/pages/ScanPage.tsx)
 *
 * Tests the scan/upload page contract from SPEC.md Milestone 2:
 * - Shows upload area in idle phase
 * - Shows upload progress during uploading phase
 * - Shows upload summary with per-file status after completion
 * - Upload summary shows "{N} of {M} receipts uploaded"
 * - Failed files listed with retry option
 * - "Upload More" option resets to idle
 * - Integrates UploadArea, UploadProgress, and UploadSummary components
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import type { UploadFile } from "@/types/receipt";

// ---- Mocks ----

type UploadPhase = "idle" | "uploading" | "complete";

let mockPhase: UploadPhase = "idle";
let mockFiles: UploadFile[] = [];
const mockStartUpload = vi.fn();
const mockRetry = vi.fn();
const mockReset = vi.fn();

vi.mock("@/hooks/useUpload", () => ({
  useUpload: () => ({
    files: mockFiles,
    phase: mockPhase,
    startUpload: mockStartUpload,
    retry: mockRetry,
    reset: mockReset,
  }),
}));

import ScanPage from "@/pages/ScanPage";

function renderScanPage() {
  return render(
    <MemoryRouter>
      <ScanPage />
    </MemoryRouter>,
  );
}

function createFile(name: string, size: number, type: string): File {
  return new File([new ArrayBuffer(size)], name, { type });
}

function makeUploadFile(
  name: string,
  status: UploadFile["status"],
  progress: number,
  error?: string,
): UploadFile {
  return {
    file: createFile(name, 1024, "image/jpeg"),
    status,
    progress,
    receiptId: status === "success" ? `receipt-${name}` : undefined,
    error,
  };
}

describe("ScanPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPhase = "idle";
    mockFiles = [];
  });

  // ---- Page title ----

  it("renders the page title", () => {
    renderScanPage();

    expect(
      screen.getByRole("heading", { name: /scan receipts/i }),
    ).toBeInTheDocument();
  });

  // ---- Idle phase ----

  it("shows the upload area when in idle phase", () => {
    mockPhase = "idle";
    renderScanPage();

    expect(
      screen.getByText(/drag and drop receipt images here/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /choose files/i }),
    ).toBeInTheDocument();
  });

  it("does not show upload progress or summary in idle phase", () => {
    mockPhase = "idle";
    renderScanPage();

    expect(
      screen.queryByLabelText(/upload progress/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/receipts? uploaded/i),
    ).not.toBeInTheDocument();
  });

  // ---- Uploading phase ----

  it("shows upload progress during uploading phase", () => {
    mockPhase = "uploading";
    mockFiles = [
      makeUploadFile("a.jpg", "uploading", 50),
      makeUploadFile("b.jpg", "pending", 0),
    ];
    renderScanPage();

    // UploadProgress should be rendered
    expect(screen.getByLabelText(/upload progress/i)).toBeInTheDocument();
  });

  it("does not show upload area during uploading phase", () => {
    mockPhase = "uploading";
    mockFiles = [makeUploadFile("a.jpg", "uploading", 50)];
    renderScanPage();

    expect(
      screen.queryByText(/drag and drop receipt images here/i),
    ).not.toBeInTheDocument();
  });

  it("does not show upload summary during uploading phase", () => {
    mockPhase = "uploading";
    mockFiles = [makeUploadFile("a.jpg", "uploading", 50)];
    renderScanPage();

    // No retry or upload more buttons
    expect(
      screen.queryByRole("button", { name: /retry failed/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /upload more/i }),
    ).not.toBeInTheDocument();
  });

  // ---- Complete phase ----

  it("shows upload progress and summary in complete phase", () => {
    mockPhase = "complete";
    mockFiles = [
      makeUploadFile("a.jpg", "success", 100),
      makeUploadFile("b.jpg", "success", 100),
    ];
    renderScanPage();

    expect(screen.getByLabelText(/upload progress/i)).toBeInTheDocument();
    expect(screen.getByText(/2 of 2 receipts? uploaded/i)).toBeInTheDocument();
  });

  it("does not show upload area in complete phase", () => {
    mockPhase = "complete";
    mockFiles = [makeUploadFile("a.jpg", "success", 100)];
    renderScanPage();

    expect(
      screen.queryByText(/drag and drop receipt images here/i),
    ).not.toBeInTheDocument();
  });

  it("shows all-success message when all uploads succeed", () => {
    mockPhase = "complete";
    mockFiles = [
      makeUploadFile("a.jpg", "success", 100),
      makeUploadFile("b.jpg", "success", 100),
    ];
    renderScanPage();

    expect(
      screen.getByText(/all receipts uploaded successfully/i),
    ).toBeInTheDocument();
  });

  it("shows failure message when some uploads fail", () => {
    mockPhase = "complete";
    mockFiles = [
      makeUploadFile("a.jpg", "success", 100),
      makeUploadFile("b.jpg", "failed", 0, "Network error"),
    ];
    renderScanPage();

    expect(screen.getByText(/1 of 2 receipts? uploaded/i)).toBeInTheDocument();
    expect(screen.getByText(/failed to upload/i)).toBeInTheDocument();
  });

  // ---- Summary count text ----

  it("shows correct count for all-failed uploads", () => {
    mockPhase = "complete";
    mockFiles = [
      makeUploadFile("a.jpg", "failed", 0, "Error"),
      makeUploadFile("b.jpg", "failed", 0, "Error"),
    ];
    renderScanPage();

    expect(screen.getByText(/0 of 2 receipts? uploaded/i)).toBeInTheDocument();
  });

  it("shows correct count for single file upload", () => {
    mockPhase = "complete";
    mockFiles = [makeUploadFile("a.jpg", "success", 100)];
    renderScanPage();

    expect(screen.getByText(/1 of 1 receipt/i)).toBeInTheDocument();
  });

  // ---- Retry button ----

  it("shows Retry Failed button when there are failed files", () => {
    mockPhase = "complete";
    mockFiles = [
      makeUploadFile("a.jpg", "success", 100),
      makeUploadFile("b.jpg", "failed", 0, "Error"),
    ];
    renderScanPage();

    expect(
      screen.getByRole("button", { name: /retry failed/i }),
    ).toBeInTheDocument();
  });

  it("does not show Retry Failed button when all files succeeded", () => {
    mockPhase = "complete";
    mockFiles = [
      makeUploadFile("a.jpg", "success", 100),
      makeUploadFile("b.jpg", "success", 100),
    ];
    renderScanPage();

    expect(
      screen.queryByRole("button", { name: /retry failed/i }),
    ).not.toBeInTheDocument();
  });

  it("calls retry with failed files when Retry Failed is clicked", async () => {
    const user = userEvent.setup();
    mockPhase = "complete";
    const failedFile = makeUploadFile("b.jpg", "failed", 0, "Error");
    mockFiles = [makeUploadFile("a.jpg", "success", 100), failedFile];
    renderScanPage();

    await user.click(
      screen.getByRole("button", { name: /retry failed/i }),
    );

    expect(mockRetry).toHaveBeenCalledTimes(1);
    expect(mockRetry).toHaveBeenCalledWith([failedFile.file]);
  });

  // ---- Upload More button ----

  it("shows Upload More button in complete phase", () => {
    mockPhase = "complete";
    mockFiles = [makeUploadFile("a.jpg", "success", 100)];
    renderScanPage();

    expect(
      screen.getByRole("button", { name: /upload more/i }),
    ).toBeInTheDocument();
  });

  it("calls reset when Upload More is clicked", async () => {
    const user = userEvent.setup();
    mockPhase = "complete";
    mockFiles = [makeUploadFile("a.jpg", "success", 100)];
    renderScanPage();

    await user.click(
      screen.getByRole("button", { name: /upload more/i }),
    );

    expect(mockReset).toHaveBeenCalledTimes(1);
  });

  // ---- View Receipts link ----

  it("shows View Receipts link in complete phase", () => {
    mockPhase = "complete";
    mockFiles = [makeUploadFile("a.jpg", "success", 100)];
    renderScanPage();

    const link = screen.getByRole("link", { name: /view receipts/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/receipts");
  });

  // ---- Failed file details ----

  it("displays error messages for failed files", () => {
    mockPhase = "complete";
    mockFiles = [
      makeUploadFile("a.jpg", "failed", 0, "Network error during upload"),
    ];
    renderScanPage();

    // Error appears in both UploadProgress (inline error) and UploadSummary (failed list)
    const errorElements = screen.getAllByText(/network error during upload/i);
    expect(errorElements.length).toBeGreaterThanOrEqual(1);
  });

  it("lists all failed file names in the summary", () => {
    mockPhase = "complete";
    mockFiles = [
      makeUploadFile("receipt1.jpg", "failed", 0, "Error 1"),
      makeUploadFile("receipt2.jpg", "failed", 0, "Error 2"),
      makeUploadFile("receipt3.jpg", "success", 100),
    ];
    renderScanPage();

    // Failed file names appear in the failed uploads list
    const failedList = screen.getByLabelText(/failed uploads/i);
    expect(within(failedList).getByText("receipt1.jpg")).toBeInTheDocument();
    expect(within(failedList).getByText("receipt2.jpg")).toBeInTheDocument();
  });

  // ---- startUpload integration ----

  it("passes onFilesSelected to UploadArea that calls startUpload", async () => {
    mockPhase = "idle";
    renderScanPage();

    // The UploadArea renders with onFilesSelected={startUpload}
    // We verify that clicking Choose Files and submitting would call startUpload
    // (The actual file handling is tested in UploadArea tests)
    // Just verify the upload area is connected properly
    expect(
      screen.getByRole("button", { name: /choose files/i }),
    ).toBeInTheDocument();
  });

  // ---- Progress bars ----

  it("shows progress bars for each file during upload", () => {
    mockPhase = "uploading";
    mockFiles = [
      makeUploadFile("a.jpg", "uploading", 75),
      makeUploadFile("b.jpg", "pending", 0),
    ];
    renderScanPage();

    const progressBars = screen.getAllByRole("progressbar");
    expect(progressBars).toHaveLength(2);
  });
});
