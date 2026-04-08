/**
 * PipelineComparison tests (frontend/src/components/PipelineComparison.tsx)
 *
 * Tests the pipeline comparison toggle contract from SPEC.md Milestone 4:
 * - Toggle expands/collapses the comparison panel
 * - Displays both OCR-AI and AI-multimodal pipeline results
 * - Shows ranking winner
 * - Shows confidence scores and processing time
 * - Handles case where one pipeline result is null (pipeline failed)
 * - Shows loading state while fetching pipeline results
 * - Handles error fetching pipeline results
 * - Fetches results only when expanded (lazy loading)
 *
 * Spec references:
 * - SPEC.md >> Milestone 4: Pipeline comparison toggle (staff only)
 * - api-contracts.md >> GET /api/receipts/{id}/pipeline-results
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PipelineResultsResponse } from "@/api/categories";

// ---- Mocks ----

const mockFetchPipelineResults = vi.fn();

vi.mock("@/api/categories", () => ({
  fetchCategories: vi.fn().mockResolvedValue({ categories: [] }),
  createCategory: vi.fn(),
  deleteCategory: vi.fn(),
  fetchPipelineResults: (...args: unknown[]) =>
    mockFetchPipelineResults(...args),
}));

vi.mock("@/lib/auth", () => ({
  getValidIdToken: vi.fn().mockResolvedValue("mock-token"),
}));

import PipelineComparison from "@/components/PipelineComparison";

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });
}

function renderPipeline(receiptId = "01HQ3K5P7M2N4R6S8T0V") {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <PipelineComparison receiptId={receiptId} />
    </QueryClientProvider>,
  );
}

function makePipelineResults(
  overrides: Partial<PipelineResultsResponse> = {},
): PipelineResultsResponse {
  return {
    receiptId: "01HQ3K5P7M2N4R6S8T0V",
    usedFallback: false,
    rankingWinner: "ocr-ai",
    results: {
      "ocr-ai": {
        extractedData: {
          merchant: { name: "Whole Foods Market", address: "123 Main St" },
          receiptDate: "2026-03-25",
          lineItems: [],
          total: 30.39,
          category: "groceries-food",
          subcategory: "supermarket-grocery",
          confidence: 0.94,
        },
        confidence: 0.94,
        rankingScore: 0.91,
        processingTimeMs: 4523,
        modelId: "amazon.nova-lite-v1:0",
        createdAt: "2026-03-25T14:30:45Z",
      },
      "ai-multimodal": {
        extractedData: {
          merchant: { name: "Whole Foods", address: "123 Main St" },
          receiptDate: "2026-03-25",
          lineItems: [],
          total: 30.39,
          category: "groceries-food",
          subcategory: "supermarket-grocery",
          confidence: 0.89,
        },
        confidence: 0.89,
        rankingScore: 0.82,
        processingTimeMs: 2100,
        modelId: "amazon.nova-lite-v1:0",
        createdAt: "2026-03-25T14:30:43Z",
      },
    },
    ...overrides,
  };
}

describe("PipelineComparison", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ---- Toggle behavior ----

  it("renders a toggle button for pipeline comparison", () => {
    renderPipeline();

    const toggle = screen.getByRole("button");
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveTextContent(/pipeline comparison/i);
  });

  it("starts in collapsed state (aria-expanded=false)", () => {
    renderPipeline();

    const toggle = screen.getByRole("button");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  it("expands when toggle is clicked (aria-expanded=true)", async () => {
    const user = userEvent.setup();
    mockFetchPipelineResults.mockResolvedValue(makePipelineResults());
    renderPipeline();

    const toggle = screen.getByRole("button");
    await user.click(toggle);

    expect(toggle).toHaveAttribute("aria-expanded", "true");
  });

  it("collapses when toggle is clicked again", async () => {
    const user = userEvent.setup();
    mockFetchPipelineResults.mockResolvedValue(makePipelineResults());
    renderPipeline();

    const toggle = screen.getByRole("button");

    // Expand
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");

    // Collapse
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  // ---- Lazy fetching ----

  it("does not fetch pipeline results while collapsed", () => {
    renderPipeline();

    expect(mockFetchPipelineResults).not.toHaveBeenCalled();
  });

  it("fetches pipeline results when expanded", async () => {
    const user = userEvent.setup();
    mockFetchPipelineResults.mockResolvedValue(makePipelineResults());
    renderPipeline();

    const toggle = screen.getByRole("button");
    await user.click(toggle);

    await waitFor(() => {
      expect(mockFetchPipelineResults).toHaveBeenCalledWith(
        "01HQ3K5P7M2N4R6S8T0V",
      );
    });
  });

  // ---- Displaying both pipeline results ----

  it("displays OCR+AI and AI Multimodal pipeline labels", async () => {
    const user = userEvent.setup();
    mockFetchPipelineResults.mockResolvedValue(makePipelineResults());
    renderPipeline();

    const toggle = screen.getByRole("button");
    await user.click(toggle);

    await waitFor(() => {
      // The component labels them as "OCR + AI" and "AI Multimodal"
      const allText = document.body.textContent;
      expect(allText).toContain("OCR");
      expect(allText).toContain("Multimodal");
    });
  });

  it("displays ranking winner indicator", async () => {
    const user = userEvent.setup();
    mockFetchPipelineResults.mockResolvedValue(
      makePipelineResults({ rankingWinner: "ocr-ai" }),
    );
    renderPipeline();

    const toggle = screen.getByRole("button");
    await user.click(toggle);

    await waitFor(() => {
      // "Winner" appears multiple times (badge + label) -- just check it's present
      expect(screen.getAllByText(/winner/i).length).toBeGreaterThan(0);
    });
  });

  it("displays confidence scores as percentages", async () => {
    const user = userEvent.setup();
    mockFetchPipelineResults.mockResolvedValue(makePipelineResults());
    renderPipeline();

    const toggle = screen.getByRole("button");
    await user.click(toggle);

    await waitFor(() => {
      // Confidence 0.94 = 94.0%, 0.89 = 89.0%
      expect(screen.getByText("94.0%")).toBeInTheDocument();
      expect(screen.getByText("89.0%")).toBeInTheDocument();
    });
  });

  it("displays processing times", async () => {
    const user = userEvent.setup();
    mockFetchPipelineResults.mockResolvedValue(makePipelineResults());
    renderPipeline();

    const toggle = screen.getByRole("button");
    await user.click(toggle);

    await waitFor(() => {
      // 4523ms = 4.5s, 2100ms = 2.1s
      expect(screen.getByText("4.5s")).toBeInTheDocument();
      expect(screen.getByText("2.1s")).toBeInTheDocument();
    });
  });

  it("displays ranking scores as percentages", async () => {
    const user = userEvent.setup();
    mockFetchPipelineResults.mockResolvedValue(makePipelineResults());
    renderPipeline();

    const toggle = screen.getByRole("button");
    await user.click(toggle);

    await waitFor(() => {
      // rankingScore 0.91 = 91.0%, 0.82 = 82.0%
      expect(screen.getByText("91.0%")).toBeInTheDocument();
      expect(screen.getByText("82.0%")).toBeInTheDocument();
    });
  });

  // ---- One pipeline result is null (failed) ----

  it("handles null ocr-ai pipeline result gracefully", async () => {
    const user = userEvent.setup();
    const results = makePipelineResults();
    results.results["ocr-ai"] = undefined;
    mockFetchPipelineResults.mockResolvedValue(results);
    renderPipeline();

    const toggle = screen.getByRole("button");
    await user.click(toggle);

    await waitFor(() => {
      // Should still render without crashing
      // The ai-multimodal results should still show
      const bodyText = document.body.textContent;
      expect(bodyText).toContain("Multimodal");
    });
  });

  it("handles null ai-multimodal pipeline result gracefully", async () => {
    const user = userEvent.setup();
    const results = makePipelineResults();
    results.results["ai-multimodal"] = undefined;
    mockFetchPipelineResults.mockResolvedValue(results);
    renderPipeline();

    const toggle = screen.getByRole("button");
    await user.click(toggle);

    await waitFor(() => {
      // Should still render without crashing
      // The ocr-ai results should still show
      const bodyText = document.body.textContent;
      expect(bodyText).toContain("OCR");
    });
  });

  // ---- Loading state ----

  it("shows loading indicator while fetching pipeline results", async () => {
    const user = userEvent.setup();
    mockFetchPipelineResults.mockReturnValue(new Promise(() => {}));
    renderPipeline();

    const toggle = screen.getByRole("button");
    await user.click(toggle);

    // Should show some loading indicator (spinner, status role, etc.)
    await waitFor(() => {
      const status = screen.queryByRole("status");
      const spinner = document.querySelector("[class*=animate-spin]");
      expect(status || spinner).toBeTruthy();
    });
  });

  // ---- Error state ----

  it("shows error message when pipeline results fetch fails", async () => {
    const user = userEvent.setup();
    mockFetchPipelineResults.mockRejectedValue(
      new Error("Failed to fetch pipeline results"),
    );
    renderPipeline();

    const toggle = screen.getByRole("button");
    await user.click(toggle);

    await waitFor(() => {
      expect(screen.getByText(/error|failed/i)).toBeInTheDocument();
    });
  });

  // ---- Used fallback indicator ----

  it("shows fallback indicator when usedFallback is true", async () => {
    const user = userEvent.setup();
    mockFetchPipelineResults.mockResolvedValue(
      makePipelineResults({ usedFallback: true }),
    );
    renderPipeline();

    const toggle = screen.getByRole("button");
    await user.click(toggle);

    await waitFor(() => {
      expect(screen.getByText(/fallback/i)).toBeInTheDocument();
    });
  });

  // ---- Merchant data displayed in comparison ----

  it("displays extracted merchant names from both pipelines", async () => {
    const user = userEvent.setup();
    mockFetchPipelineResults.mockResolvedValue(makePipelineResults());
    renderPipeline();

    const toggle = screen.getByRole("button");
    await user.click(toggle);

    await waitFor(() => {
      expect(screen.getByText("Whole Foods Market")).toBeInTheDocument();
      expect(screen.getByText("Whole Foods")).toBeInTheDocument();
    });
  });
});
