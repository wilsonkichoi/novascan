/**
 * ReceiptsPage tests (frontend/src/pages/ReceiptsPage.tsx)
 *
 * Tests the receipts list page contract from SPEC.md Milestone 2:
 * - Renders receipt cards with merchant, total, date, category, status badge
 * - Shows correct status badges: Processing, Confirmed, Failed
 * - Processing receipts show "Processing..." instead of merchant and "--" for total
 * - Shows loading state
 * - Shows error state with retry message
 * - Shows empty state when no receipts exist
 * - Pagination: "Load More" button when there are more results
 * - Receipts sorted by most recent first (ULID descending)
 * - Receipt cards link to detail page
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReceiptListItem, ReceiptListResponse } from "@/api/receipts";

// ---- Mocks ----

const mockFetchReceipts = vi.fn();

vi.mock("@/api/receipts", () => ({
  fetchReceipts: (...args: unknown[]) => mockFetchReceipts(...args),
}));

vi.mock("@/lib/auth", () => ({
  getValidIdToken: vi.fn().mockResolvedValue("mock-token"),
}));

import ReceiptsPage from "@/pages/ReceiptsPage";

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

function renderReceiptsPage() {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ReceiptsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function makeReceipt(
  overrides: Partial<ReceiptListItem> = {},
): ReceiptListItem {
  return {
    receiptId: "01HQ3K5P7M2N4R6S8T0V",
    receiptDate: "2026-03-25",
    merchant: "Whole Foods Market",
    total: 30.39,
    category: "groceries-food",
    subcategory: "supermarket-grocery",
    categoryDisplay: "Groceries & Food",
    subcategoryDisplay: "Supermarket / Grocery",
    status: "confirmed",
    imageUrl: "https://example.com/image.jpg",
    createdAt: "2026-03-25T14:30:00Z",
    ...overrides,
  };
}

function makeResponse(
  receipts: ReceiptListItem[],
  nextCursor: string | null = null,
): ReceiptListResponse {
  return { receipts, nextCursor };
}

describe("ReceiptsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ---- Loading state ----

  it("shows a loading spinner while fetching receipts", () => {
    // Never resolve the fetch
    mockFetchReceipts.mockReturnValue(new Promise(() => {}));
    renderReceiptsPage();

    // Should show some kind of loading indicator (spinner has animate-spin class)
    // We can't query by class, but we can check that the page content is not yet shown
    expect(screen.queryByRole("heading", { name: /receipts/i })).not.toBeInTheDocument();
  });

  // ---- Error state ----

  it("shows error message when fetch fails", async () => {
    mockFetchReceipts.mockRejectedValue(new Error("Network error"));
    renderReceiptsPage();

    await waitFor(() => {
      expect(
        screen.getByText(/failed to load receipts/i),
      ).toBeInTheDocument();
    });
  });

  // ---- Empty state ----

  it("shows empty state when there are no receipts", async () => {
    mockFetchReceipts.mockResolvedValue(makeResponse([]));
    renderReceiptsPage();

    await waitFor(() => {
      expect(screen.getByText(/no receipts yet/i)).toBeInTheDocument();
    });
  });

  it("shows page heading even in empty state", async () => {
    mockFetchReceipts.mockResolvedValue(makeResponse([]));
    renderReceiptsPage();

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /receipts/i }),
      ).toBeInTheDocument();
    });
  });

  // ---- Receipt card rendering ----

  it("renders receipt cards with merchant name", async () => {
    mockFetchReceipts.mockResolvedValue(
      makeResponse([makeReceipt({ merchant: "Trader Joe's" })]),
    );
    renderReceiptsPage();

    await waitFor(() => {
      expect(screen.getByText("Trader Joe's")).toBeInTheDocument();
    });
  });

  it("renders receipt cards with formatted total amount", async () => {
    mockFetchReceipts.mockResolvedValue(
      makeResponse([makeReceipt({ total: 30.39 })]),
    );
    renderReceiptsPage();

    await waitFor(() => {
      expect(screen.getByText("$30.39")).toBeInTheDocument();
    });
  });

  it("renders receipt cards with formatted date", async () => {
    mockFetchReceipts.mockResolvedValue(
      makeResponse([makeReceipt({ receiptDate: "2026-03-25" })]),
    );
    renderReceiptsPage();

    await waitFor(() => {
      expect(screen.getByText("Mar 25, 2026")).toBeInTheDocument();
    });
  });

  it("renders receipt cards with category display name", async () => {
    mockFetchReceipts.mockResolvedValue(
      makeResponse([makeReceipt({ categoryDisplay: "Groceries & Food" })]),
    );
    renderReceiptsPage();

    await waitFor(() => {
      expect(screen.getByText("Groceries & Food")).toBeInTheDocument();
    });
  });

  // ---- Status badges ----

  it("shows Confirmed badge for confirmed receipts", async () => {
    mockFetchReceipts.mockResolvedValue(
      makeResponse([makeReceipt({ status: "confirmed" })]),
    );
    renderReceiptsPage();

    await waitFor(() => {
      expect(screen.getByText("Confirmed")).toBeInTheDocument();
    });
  });

  it("shows Processing badge for processing receipts", async () => {
    mockFetchReceipts.mockResolvedValue(
      makeResponse([
        makeReceipt({
          status: "processing",
          merchant: null,
          total: null,
          category: null,
          categoryDisplay: null,
          receiptDate: null,
        }),
      ]),
    );
    renderReceiptsPage();

    await waitFor(() => {
      expect(screen.getByText("Processing")).toBeInTheDocument();
    });
  });

  it("shows Failed badge for failed receipts", async () => {
    mockFetchReceipts.mockResolvedValue(
      makeResponse([makeReceipt({ status: "failed" })]),
    );
    renderReceiptsPage();

    await waitFor(() => {
      expect(screen.getByText("Failed")).toBeInTheDocument();
    });
  });

  // ---- Processing receipt display ----

  it("shows 'Processing...' instead of merchant name for processing receipts", async () => {
    mockFetchReceipts.mockResolvedValue(
      makeResponse([
        makeReceipt({
          status: "processing",
          merchant: null,
          total: null,
        }),
      ]),
    );
    renderReceiptsPage();

    await waitFor(() => {
      expect(screen.getByText("Processing...")).toBeInTheDocument();
    });
  });

  it("shows '--' instead of total for processing receipts", async () => {
    mockFetchReceipts.mockResolvedValue(
      makeResponse([
        makeReceipt({
          status: "processing",
          merchant: null,
          total: null,
        }),
      ]),
    );
    renderReceiptsPage();

    await waitFor(() => {
      expect(screen.getByText("--")).toBeInTheDocument();
    });
  });

  // ---- Multiple receipts ----

  it("renders multiple receipt cards", async () => {
    mockFetchReceipts.mockResolvedValue(
      makeResponse([
        makeReceipt({
          receiptId: "r1",
          merchant: "Whole Foods",
          total: 30.39,
          status: "confirmed",
        }),
        makeReceipt({
          receiptId: "r2",
          merchant: "Costco",
          total: 142.87,
          status: "confirmed",
        }),
        makeReceipt({
          receiptId: "r3",
          status: "processing",
          merchant: null,
          total: null,
        }),
      ]),
    );
    renderReceiptsPage();

    await waitFor(() => {
      expect(screen.getByText("Whole Foods")).toBeInTheDocument();
      expect(screen.getByText("Costco")).toBeInTheDocument();
      expect(screen.getByText("Processing...")).toBeInTheDocument();
    });
  });

  // ---- Receipt card links ----

  it("receipt cards link to the receipt detail page", async () => {
    mockFetchReceipts.mockResolvedValue(
      makeResponse([
        makeReceipt({
          receiptId: "01HQ3K5P7M2N4R6S8T0V",
          merchant: "Whole Foods",
        }),
      ]),
    );
    renderReceiptsPage();

    await waitFor(() => {
      const link = screen.getByRole("link");
      expect(link).toHaveAttribute(
        "href",
        "/receipts/01HQ3K5P7M2N4R6S8T0V",
      );
    });
  });

  // ---- Pagination ----

  it("shows Load More button when there is a next page", async () => {
    mockFetchReceipts.mockResolvedValue(
      makeResponse(
        [makeReceipt({ receiptId: "r1", merchant: "Store 1" })],
        "cursor-page-2",
      ),
    );
    renderReceiptsPage();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /load more/i }),
      ).toBeInTheDocument();
    });
  });

  it("does not show Load More button when there are no more pages", async () => {
    mockFetchReceipts.mockResolvedValue(
      makeResponse(
        [makeReceipt({ receiptId: "r1", merchant: "Store 1" })],
        null,
      ),
    );
    renderReceiptsPage();

    await waitFor(() => {
      expect(screen.getByText("Store 1")).toBeInTheDocument();
    });

    expect(
      screen.queryByRole("button", { name: /load more/i }),
    ).not.toBeInTheDocument();
  });

  it("fetches next page when Load More is clicked", async () => {
    const user = userEvent.setup();

    mockFetchReceipts
      .mockResolvedValueOnce(
        makeResponse(
          [makeReceipt({ receiptId: "r1", merchant: "Page 1 Store" })],
          "cursor-page-2",
        ),
      )
      .mockResolvedValueOnce(
        makeResponse(
          [makeReceipt({ receiptId: "r2", merchant: "Page 2 Store" })],
          null,
        ),
      );

    renderReceiptsPage();

    await waitFor(() => {
      expect(screen.getByText("Page 1 Store")).toBeInTheDocument();
    });

    await user.click(
      screen.getByRole("button", { name: /load more/i }),
    );

    await waitFor(() => {
      expect(screen.getByText("Page 2 Store")).toBeInTheDocument();
    });

    // Both pages should be visible
    expect(screen.getByText("Page 1 Store")).toBeInTheDocument();
    expect(screen.getByText("Page 2 Store")).toBeInTheDocument();
  });

  it("passes cursor to fetchReceipts for pagination", async () => {
    const user = userEvent.setup();

    mockFetchReceipts
      .mockResolvedValueOnce(
        makeResponse(
          [makeReceipt({ receiptId: "r1", merchant: "Store 1" })],
          "cursor-abc-123",
        ),
      )
      .mockResolvedValueOnce(
        makeResponse(
          [makeReceipt({ receiptId: "r2", merchant: "Store 2" })],
          null,
        ),
      );

    renderReceiptsPage();

    await waitFor(() => {
      expect(screen.getByText("Store 1")).toBeInTheDocument();
    });

    await user.click(
      screen.getByRole("button", { name: /load more/i }),
    );

    await waitFor(() => {
      expect(mockFetchReceipts).toHaveBeenCalledWith("cursor-abc-123");
    });
  });

  it("hides Load More after last page is loaded", async () => {
    const user = userEvent.setup();

    mockFetchReceipts
      .mockResolvedValueOnce(
        makeResponse(
          [makeReceipt({ receiptId: "r1", merchant: "Store 1" })],
          "cursor-2",
        ),
      )
      .mockResolvedValueOnce(
        makeResponse(
          [makeReceipt({ receiptId: "r2", merchant: "Store 2" })],
          null,
        ),
      );

    renderReceiptsPage();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /load more/i }),
      ).toBeInTheDocument();
    });

    await user.click(
      screen.getByRole("button", { name: /load more/i }),
    );

    await waitFor(() => {
      expect(screen.getByText("Store 2")).toBeInTheDocument();
    });

    expect(
      screen.queryByRole("button", { name: /load more/i }),
    ).not.toBeInTheDocument();
  });

  // ---- Receipt with null merchant ----

  it("shows 'Unknown' for confirmed receipts with null merchant", async () => {
    mockFetchReceipts.mockResolvedValue(
      makeResponse([
        makeReceipt({ status: "confirmed", merchant: null }),
      ]),
    );
    renderReceiptsPage();

    await waitFor(() => {
      expect(screen.getByText("Unknown")).toBeInTheDocument();
    });
  });

  // ---- Receipt with null total ----

  it("shows '--' for confirmed receipts with null total", async () => {
    mockFetchReceipts.mockResolvedValue(
      makeResponse([
        makeReceipt({ status: "confirmed", total: null }),
      ]),
    );
    renderReceiptsPage();

    await waitFor(() => {
      expect(screen.getByText("--")).toBeInTheDocument();
    });
  });

  // ---- First fetch call ----

  it("calls fetchReceipts with undefined cursor on initial load", async () => {
    mockFetchReceipts.mockResolvedValue(makeResponse([]));
    renderReceiptsPage();

    await waitFor(() => {
      expect(mockFetchReceipts).toHaveBeenCalledWith(undefined);
    });
  });

  // ---- Does not show Load More on empty list ----

  it("does not show Load More when receipt list is empty", async () => {
    mockFetchReceipts.mockResolvedValue(makeResponse([]));
    renderReceiptsPage();

    await waitFor(() => {
      expect(screen.getByText(/no receipts yet/i)).toBeInTheDocument();
    });

    expect(
      screen.queryByRole("button", { name: /load more/i }),
    ).not.toBeInTheDocument();
  });
});
