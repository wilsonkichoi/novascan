/**
 * useUpload hook tests (frontend/src/hooks/useUpload.ts)
 *
 * Tests the upload flow contract from SPEC.md Milestone 2:
 * - Calls POST /api/receipts/upload-urls API to get presigned URLs
 * - Uploads files to presigned S3 URLs
 * - Retries failed uploads up to 3 times with exponential backoff (1s, 2s, 4s)
 * - Requests new presigned URL on expiry (when upload fails)
 * - Tracks per-file upload status (pending, uploading, success, failed)
 * - Phase transitions: idle -> uploading -> complete
 * - Retry mechanism for failed files
 * - Reset returns to idle state
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useUpload } from "@/hooks/useUpload";

// Mock the API module
const mockRequestUploadUrls = vi.fn();
const mockUploadFileToS3 = vi.fn();

vi.mock("@/api/receipts", () => ({
  requestUploadUrls: (...args: unknown[]) => mockRequestUploadUrls(...args),
  uploadFileToS3: (...args: unknown[]) => mockUploadFileToS3(...args),
}));

function createFile(name: string, size: number, type: string): File {
  const buffer = new ArrayBuffer(size);
  return new File([buffer], name, { type });
}

function makeUploadUrlReceipt(receiptId: string, _index: number) {
  return {
    receiptId,
    uploadUrl: `https://s3.example.com/presigned-${receiptId}`,
    imageKey: `receipts/${receiptId}.jpg`,
    expiresIn: 900,
  };
}

describe("useUpload", () => {
  // Store original setTimeout so we can restore it
  const originalSetTimeout = globalThis.setTimeout;

  beforeEach(() => {
    vi.clearAllMocks();
    // Replace setTimeout to resolve immediately, eliminating backoff delays
    // while preserving the retry logic behavior. This lets us test the retry
    // contract without waiting 7+ seconds.
    globalThis.setTimeout = ((fn: () => void, _ms?: number) => {
      // Execute callback on next microtask to preserve async ordering
      Promise.resolve().then(fn);
      return 0 as unknown as ReturnType<typeof setTimeout>;
    }) as typeof setTimeout;
  });

  afterEach(() => {
    globalThis.setTimeout = originalSetTimeout;
  });

  // ---- Initial state ----

  it("starts in idle phase with empty files", () => {
    const { result } = renderHook(() => useUpload());

    expect(result.current.phase).toBe("idle");
    expect(result.current.files).toEqual([]);
  });

  // ---- Successful upload flow ----

  it("transitions through idle -> uploading -> complete on success", async () => {
    const file = createFile("receipt.jpg", 1024, "image/jpeg");

    mockRequestUploadUrls.mockResolvedValue([
      makeUploadUrlReceipt("receipt-1", 0),
    ]);
    mockUploadFileToS3.mockResolvedValue(undefined);

    const { result } = renderHook(() => useUpload());

    expect(result.current.phase).toBe("idle");

    await act(async () => {
      await result.current.startUpload([file]);
    });

    expect(result.current.phase).toBe("complete");
  });

  it("calls requestUploadUrls with the selected files", async () => {
    const files = [
      createFile("a.jpg", 1024, "image/jpeg"),
      createFile("b.png", 2048, "image/png"),
    ];

    mockRequestUploadUrls.mockResolvedValue([
      makeUploadUrlReceipt("r1", 0),
      makeUploadUrlReceipt("r2", 1),
    ]);
    mockUploadFileToS3.mockResolvedValue(undefined);

    const { result } = renderHook(() => useUpload());

    await act(async () => {
      await result.current.startUpload(files);
    });

    expect(mockRequestUploadUrls).toHaveBeenCalledWith(files);
  });

  it("uploads each file to its presigned URL via uploadFileToS3", async () => {
    const files = [
      createFile("a.jpg", 1024, "image/jpeg"),
      createFile("b.png", 2048, "image/png"),
    ];

    mockRequestUploadUrls.mockResolvedValue([
      makeUploadUrlReceipt("r1", 0),
      makeUploadUrlReceipt("r2", 1),
    ]);
    mockUploadFileToS3.mockResolvedValue(undefined);

    const { result } = renderHook(() => useUpload());

    await act(async () => {
      await result.current.startUpload(files);
    });

    // uploadFileToS3 called once per file
    expect(mockUploadFileToS3).toHaveBeenCalledTimes(2);
    expect(mockUploadFileToS3).toHaveBeenCalledWith(
      "https://s3.example.com/presigned-r1",
      files[0],
      expect.any(Function),
    );
    expect(mockUploadFileToS3).toHaveBeenCalledWith(
      "https://s3.example.com/presigned-r2",
      files[1],
      expect.any(Function),
    );
  });

  it("marks files as success after successful upload", async () => {
    const file = createFile("receipt.jpg", 1024, "image/jpeg");

    mockRequestUploadUrls.mockResolvedValue([
      makeUploadUrlReceipt("r1", 0),
    ]);
    mockUploadFileToS3.mockResolvedValue(undefined);

    const { result } = renderHook(() => useUpload());

    await act(async () => {
      await result.current.startUpload([file]);
    });

    expect(result.current.files).toHaveLength(1);
    expect(result.current.files[0].status).toBe("success");
    expect(result.current.files[0].progress).toBe(100);
  });

  // ---- Retry on upload failure ----

  it("retries failed uploads up to 3 times", async () => {
    const file = createFile("receipt.jpg", 1024, "image/jpeg");

    mockRequestUploadUrls.mockResolvedValue([
      makeUploadUrlReceipt("r1", 0),
    ]);

    // Fail first 3 attempts, succeed on 4th (attempt index 3)
    mockUploadFileToS3
      .mockRejectedValueOnce(new Error("Network error"))
      .mockRejectedValueOnce(new Error("Network error"))
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValueOnce(undefined);

    const { result } = renderHook(() => useUpload());

    await act(async () => {
      await result.current.startUpload([file]);
    });

    // Should succeed after retries (initial attempt + 3 retries = 4 calls)
    expect(mockUploadFileToS3).toHaveBeenCalledTimes(4);
    expect(result.current.files[0].status).toBe("success");
  });

  it("marks file as failed after exhausting all retries", async () => {
    const file = createFile("receipt.jpg", 1024, "image/jpeg");

    mockRequestUploadUrls.mockResolvedValue([
      makeUploadUrlReceipt("r1", 0),
    ]);

    // Fail all 4 attempts (initial + 3 retries)
    mockUploadFileToS3.mockRejectedValue(new Error("S3 upload failed"));

    const { result } = renderHook(() => useUpload());

    await act(async () => {
      await result.current.startUpload([file]);
    });

    expect(result.current.files[0].status).toBe("failed");
    expect(result.current.files[0].error).toBeDefined();
    expect(result.current.phase).toBe("complete");
  });

  it("requests a new presigned URL when upload fails (URL may have expired)", async () => {
    const file = createFile("receipt.jpg", 1024, "image/jpeg");

    // First bulk request succeeds
    mockRequestUploadUrls
      .mockResolvedValueOnce([makeUploadUrlReceipt("r1", 0)])
      // Second request for fresh URL (after failure clears cached URL)
      .mockResolvedValueOnce([makeUploadUrlReceipt("r1-new", 0)]);

    // First upload fails (simulating expired presigned URL)
    mockUploadFileToS3
      .mockRejectedValueOnce(new Error("403 Forbidden"))
      .mockResolvedValueOnce(undefined);

    const { result } = renderHook(() => useUpload());

    await act(async () => {
      await result.current.startUpload([file]);
    });

    // requestUploadUrls called: once for bulk, once for fresh URL after failure
    expect(mockRequestUploadUrls).toHaveBeenCalledTimes(2);
    expect(result.current.files[0].status).toBe("success");
  });

  // ---- Bulk request failure ----

  it("falls back to individual URL requests when bulk request fails", async () => {
    const file = createFile("receipt.jpg", 1024, "image/jpeg");

    // Bulk request fails
    mockRequestUploadUrls
      .mockRejectedValueOnce(new Error("Server error"))
      // Individual request succeeds
      .mockResolvedValueOnce([makeUploadUrlReceipt("r1", 0)]);

    mockUploadFileToS3.mockResolvedValue(undefined);

    const { result } = renderHook(() => useUpload());

    await act(async () => {
      await result.current.startUpload([file]);
    });

    expect(result.current.files[0].status).toBe("success");
  });

  // ---- Per-file status tracking ----

  it("tracks each file independently in a multi-file upload", async () => {
    const files = [
      createFile("good.jpg", 1024, "image/jpeg"),
      createFile("bad.jpg", 2048, "image/jpeg"),
    ];

    mockRequestUploadUrls.mockResolvedValue([
      makeUploadUrlReceipt("good-receipt", 0),
      makeUploadUrlReceipt("bad-receipt", 1),
    ]);

    // First file (good-receipt) succeeds, second (bad-receipt) always fails.
    // We use the file argument to distinguish since URLs change on retry.
    mockUploadFileToS3.mockImplementation(
      (_url: string, file: File, _onProgress: (pct: number) => void) => {
        if (file.name === "good.jpg") return Promise.resolve();
        return Promise.reject(new Error("Upload failed"));
      },
    );

    const { result } = renderHook(() => useUpload());

    await act(async () => {
      await result.current.startUpload(files);
    });

    expect(result.current.files[0].status).toBe("success");
    expect(result.current.files[1].status).toBe("failed");
    expect(result.current.phase).toBe("complete");
  });

  it("assigns receiptId from API response to file state", async () => {
    const file = createFile("receipt.jpg", 1024, "image/jpeg");

    mockRequestUploadUrls.mockResolvedValue([
      makeUploadUrlReceipt("my-receipt-id", 0),
    ]);
    mockUploadFileToS3.mockResolvedValue(undefined);

    const { result } = renderHook(() => useUpload());

    await act(async () => {
      await result.current.startUpload([file]);
    });

    expect(result.current.files[0].receiptId).toBe("my-receipt-id");
  });

  // ---- Retry mechanism ----

  it("retry resets failed files to pending and re-uploads", async () => {
    const file = createFile("receipt.jpg", 1024, "image/jpeg");

    mockRequestUploadUrls.mockResolvedValue([
      makeUploadUrlReceipt("r1", 0),
    ]);

    // First attempt fails all retries
    mockUploadFileToS3.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useUpload());

    await act(async () => {
      await result.current.startUpload([file]);
    });

    expect(result.current.files[0].status).toBe("failed");

    // Now mock success for retry
    mockUploadFileToS3.mockReset();
    mockRequestUploadUrls.mockResolvedValue([
      makeUploadUrlReceipt("r1-retry", 0),
    ]);
    mockUploadFileToS3.mockResolvedValue(undefined);

    await act(async () => {
      await result.current.retry([file]);
    });

    expect(result.current.files[0].status).toBe("success");
    expect(result.current.phase).toBe("complete");
  });

  // ---- Reset ----

  it("reset clears files and returns to idle phase", async () => {
    const file = createFile("receipt.jpg", 1024, "image/jpeg");

    mockRequestUploadUrls.mockResolvedValue([
      makeUploadUrlReceipt("r1", 0),
    ]);
    mockUploadFileToS3.mockResolvedValue(undefined);

    const { result } = renderHook(() => useUpload());

    await act(async () => {
      await result.current.startUpload([file]);
    });

    expect(result.current.phase).toBe("complete");
    expect(result.current.files).toHaveLength(1);

    act(() => {
      result.current.reset();
    });

    expect(result.current.phase).toBe("idle");
    expect(result.current.files).toEqual([]);
  });

  // ---- Error propagation ----

  it("preserves error message from upload failure", async () => {
    const file = createFile("receipt.jpg", 1024, "image/jpeg");

    mockRequestUploadUrls.mockResolvedValue([
      makeUploadUrlReceipt("r1", 0),
    ]);
    mockUploadFileToS3.mockRejectedValue(
      new Error("S3 upload failed (403)"),
    );

    const { result } = renderHook(() => useUpload());

    await act(async () => {
      await result.current.startUpload([file]);
    });

    expect(result.current.files[0].error).toContain("failed");
  });

  it("handles non-Error rejection gracefully", async () => {
    const file = createFile("receipt.jpg", 1024, "image/jpeg");

    mockRequestUploadUrls.mockResolvedValue([
      makeUploadUrlReceipt("r1", 0),
    ]);
    mockUploadFileToS3.mockRejectedValue("string error");

    const { result } = renderHook(() => useUpload());

    await act(async () => {
      await result.current.startUpload([file]);
    });

    expect(result.current.files[0].status).toBe("failed");
    expect(result.current.files[0].error).toBeDefined();
  });

  // ---- URL request failure with retries ----

  it("marks file as failed when URL request fails after all retries", async () => {
    const file = createFile("receipt.jpg", 1024, "image/jpeg");

    // Bulk request fails
    mockRequestUploadUrls.mockRejectedValue(new Error("Server error"));

    const { result } = renderHook(() => useUpload());

    await act(async () => {
      await result.current.startUpload([file]);
    });

    expect(result.current.files[0].status).toBe("failed");
    expect(result.current.phase).toBe("complete");
  });
});
