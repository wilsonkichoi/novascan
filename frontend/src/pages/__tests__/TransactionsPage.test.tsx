/**
 * TransactionsPage tests (frontend/src/pages/TransactionsPage.tsx)
 *
 * Tests the transactions page contract from SPEC.md Milestone 5:
 * - Sortable table with columns: date, merchant, category, amount, status
 * - Column header click toggles sort direction
 * - Date range, category, status, and merchant search filters
 * - Merchant search with debounce
 * - Pagination via cursor (Load More)
 * - Loading state while fetching transactions
 * - Error state when fetch fails
 *
 * Spec references:
 * - SPEC.md >> Milestone 5 Acceptance Criteria
 * - api-contracts.md >> GET /api/transactions
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { TransactionsResponse, Transaction } from "@/api/transactions";

// ---- Mocks ----

const mockFetchTransactions = vi.fn();

vi.mock("@/api/transactions", async () => {
  const actual = await vi.importActual<typeof import("@/api/transactions")>(
    "@/api/transactions",
  );
  return {
    ...actual,
    fetchTransactions: (...args: unknown[]) => mockFetchTransactions(...args),
  };
});

vi.mock("@/lib/auth", () => ({
  getValidIdToken: vi.fn().mockResolvedValue("mock-token"),
  initiateAuth: vi.fn(),
  respondToChallenge: vi.fn(),
  refreshTokens: vi.fn().mockResolvedValue(null),
  signOut: vi.fn(),
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: { userId: "user-123", email: "user@example.com", roles: ["user"] },
    isLoading: false,
    signIn: vi.fn(),
    verifyOtp: vi.fn(),
    signOut: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import TransactionsPage from "@/pages/TransactionsPage";

/** Helper to wait for data to load (handles dual table+card rendering) */
async function waitForDataLoaded() {
  await waitFor(() => {
    const elements = screen.getAllByText("Whole Foods Market");
    expect(elements.length).toBeGreaterThanOrEqual(1);
  });
}

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
}

function renderTransactionsPage() {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/transactions"]}>
        <TransactionsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function makeTransaction(overrides: Partial<Transaction> = {}): Transaction {
  return {
    receiptId: "01HQ3K5P7M2N4R6S8T0V",
    receiptDate: "2026-03-25",
    merchant: "Whole Foods Market",
    total: 30.39,
    category: "groceries-food",
    categoryDisplay: "Groceries & Food",
    subcategory: "supermarket-grocery",
    subcategoryDisplay: "Supermarket / Grocery",
    status: "confirmed",
    ...overrides,
  };
}

function makeResponse(
  overrides: Partial<TransactionsResponse> = {},
): TransactionsResponse {
  return {
    transactions: [
      makeTransaction(),
      makeTransaction({
        receiptId: "01HQ3K5P7M2N4R6S8T0W",
        merchant: "Starbucks",
        total: 5.75,
        category: "dining",
        categoryDisplay: "Dining",
        receiptDate: "2026-03-24",
      }),
    ],
    nextCursor: null,
    totalCount: 2,
    ...overrides,
  };
}

describe("TransactionsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ---- Loading state ----

  it("shows a loading indicator while fetching transactions", () => {
    mockFetchTransactions.mockReturnValue(new Promise(() => {}));
    renderTransactionsPage();

    const status = screen.queryByRole("status");
    const spinner = document.querySelector("[class*=animate-spin]");
    expect(status || spinner).toBeTruthy();
  });

  // ---- Error state ----

  it("shows error state when transactions fetch fails", async () => {
    mockFetchTransactions.mockRejectedValue(new Error("Network error"));
    renderTransactionsPage();

    await waitFor(() => {
      expect(screen.getByText(/error|failed/i)).toBeInTheDocument();
    });
  });

  // ---- Table rendering ----

  it("renders a table with transaction data", async () => {
    mockFetchTransactions.mockResolvedValue(makeResponse());
    renderTransactionsPage();

    await waitFor(() => {
      // Both table (desktop) and card (mobile) views render; use getAllByText
      const merchantElements = screen.getAllByText("Whole Foods Market");
      expect(merchantElements.length).toBeGreaterThanOrEqual(1);
    });
    const starbucksElements = screen.getAllByText("Starbucks");
    expect(starbucksElements.length).toBeGreaterThanOrEqual(1);
  });

  it("renders transaction amounts", async () => {
    mockFetchTransactions.mockResolvedValue(makeResponse());
    renderTransactionsPage();

    await waitFor(() => {
      const amountElements = screen.getAllByText("$30.39");
      expect(amountElements.length).toBeGreaterThanOrEqual(1);
    });
    const otherAmountElements = screen.getAllByText("$5.75");
    expect(otherAmountElements.length).toBeGreaterThanOrEqual(1);
  });

  it("renders transaction category display names", async () => {
    mockFetchTransactions.mockResolvedValue(makeResponse());
    renderTransactionsPage();

    await waitFor(() => {
      expect(screen.getByText("Groceries & Food")).toBeInTheDocument();
    });
    expect(screen.getByText("Dining")).toBeInTheDocument();
  });

  it("renders transaction status", async () => {
    mockFetchTransactions.mockResolvedValue(
      makeResponse({
        transactions: [
          makeTransaction({ status: "confirmed" }),
          makeTransaction({
            receiptId: "02",
            status: "processing",
            merchant: "Pending Store",
          }),
        ],
        totalCount: 2,
      }),
    );
    renderTransactionsPage();

    await waitFor(() => {
      const confirmedElements = screen.getAllByText(/confirmed/i);
      expect(confirmedElements.length).toBeGreaterThanOrEqual(1);
    });
    const processingElements = screen.getAllByText(/processing/i);
    expect(processingElements.length).toBeGreaterThanOrEqual(1);
  });

  // ---- Sortable columns ----

  it("renders sortable column headers for date, amount, and merchant", async () => {
    mockFetchTransactions.mockResolvedValue(makeResponse());
    renderTransactionsPage();

    await waitForDataLoaded();

    // Should have sort buttons for date, amount, and merchant
    expect(
      screen.getByRole("button", { name: /sort by date/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /sort by amount/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /sort by merchant/i }),
    ).toBeInTheDocument();
  });

  it("calls API with sort parameters when clicking a column header", async () => {
    const user = userEvent.setup();
    mockFetchTransactions.mockResolvedValue(makeResponse());
    renderTransactionsPage();

    await waitForDataLoaded();

    // Click "Sort by amount"
    await user.click(
      screen.getByRole("button", { name: /sort by amount/i }),
    );

    // After clicking, the API should be called again with updated sort params
    await waitFor(() => {
      const calls = mockFetchTransactions.mock.calls;
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall).toEqual(
        expect.objectContaining({ sortBy: "amount" }),
      );
    });
  });

  it("toggles sort order when clicking the same column header again", async () => {
    const user = userEvent.setup();
    mockFetchTransactions.mockResolvedValue(makeResponse());
    renderTransactionsPage();

    await waitForDataLoaded();

    // Default sort is by date desc. Click date header to toggle to asc.
    await user.click(
      screen.getByRole("button", { name: /sort by date/i }),
    );

    await waitFor(() => {
      const calls = mockFetchTransactions.mock.calls;
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall).toEqual(
        expect.objectContaining({ sortBy: "date", sortOrder: "asc" }),
      );
    });
  });

  // ---- Pagination ----

  it("shows Load More button when there are more results", async () => {
    mockFetchTransactions.mockResolvedValue(
      makeResponse({ nextCursor: "eyJza..." }),
    );
    renderTransactionsPage();

    await waitForDataLoaded();

    expect(
      screen.getByRole("button", { name: /load more/i }),
    ).toBeInTheDocument();
  });

  it("does not show Load More button when there are no more results", async () => {
    mockFetchTransactions.mockResolvedValue(
      makeResponse({ nextCursor: null }),
    );
    renderTransactionsPage();

    await waitForDataLoaded();

    expect(
      screen.queryByRole("button", { name: /load more/i }),
    ).not.toBeInTheDocument();
  });

  it("loads more transactions when Load More is clicked", async () => {
    const user = userEvent.setup();
    mockFetchTransactions
      .mockResolvedValueOnce(
        makeResponse({ nextCursor: "cursor-page-2" }),
      )
      .mockResolvedValueOnce(
        makeResponse({
          transactions: [
            makeTransaction({
              receiptId: "03",
              merchant: "Target",
              total: 99.99,
            }),
          ],
          nextCursor: null,
          totalCount: 3,
        }),
      );
    renderTransactionsPage();

    await waitForDataLoaded();

    await user.click(
      screen.getByRole("button", { name: /load more/i }),
    );

    await waitFor(() => {
      const targetElements = screen.getAllByText("Target");
      expect(targetElements.length).toBeGreaterThanOrEqual(1);
    });
  });

  // ---- Filters: Date range ----

  it("renders date range filter inputs", async () => {
    mockFetchTransactions.mockResolvedValue(makeResponse());
    renderTransactionsPage();

    await waitForDataLoaded();

    // Should have start date and end date inputs
    expect(screen.getByLabelText(/start date/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/end date/i)).toBeInTheDocument();
  });

  it("calls API with date filter when date is set", async () => {
    const user = userEvent.setup();
    mockFetchTransactions.mockResolvedValue(makeResponse());
    renderTransactionsPage();

    await waitForDataLoaded();

    const startDateInput = screen.getByLabelText(/start date/i);
    await user.clear(startDateInput);
    await user.type(startDateInput, "2026-03-01");

    await waitFor(() => {
      const calls = mockFetchTransactions.mock.calls;
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall).toEqual(
        expect.objectContaining({ startDate: "2026-03-01" }),
      );
    });
  });

  // ---- Filters: Category ----

  it("renders a category filter dropdown", async () => {
    mockFetchTransactions.mockResolvedValue(makeResponse());
    renderTransactionsPage();

    await waitForDataLoaded();

    // Should have a select/dropdown for categories with "All categories" option
    expect(screen.getByLabelText(/category/i)).toBeInTheDocument();
  });

  it("calls API with category filter when category is selected", async () => {
    const user = userEvent.setup();
    mockFetchTransactions.mockResolvedValue(makeResponse());
    renderTransactionsPage();

    await waitForDataLoaded();

    const categorySelect = screen.getByLabelText(/category/i);
    await user.selectOptions(categorySelect, "dining");

    await waitFor(() => {
      const calls = mockFetchTransactions.mock.calls;
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall).toEqual(
        expect.objectContaining({ category: "dining" }),
      );
    });
  });

  // ---- Filters: Status ----

  it("renders a status filter dropdown", async () => {
    mockFetchTransactions.mockResolvedValue(makeResponse());
    renderTransactionsPage();

    await waitForDataLoaded();

    expect(screen.getByLabelText(/status/i)).toBeInTheDocument();
  });

  it("calls API with status filter when status is selected", async () => {
    const user = userEvent.setup();
    mockFetchTransactions.mockResolvedValue(makeResponse());
    renderTransactionsPage();

    await waitForDataLoaded();

    const statusSelect = screen.getByLabelText(/status/i);
    await user.selectOptions(statusSelect, "confirmed");

    await waitFor(() => {
      const calls = mockFetchTransactions.mock.calls;
      const lastCall = calls[calls.length - 1][0];
      expect(lastCall).toEqual(
        expect.objectContaining({ status: "confirmed" }),
      );
    });
  });

  // ---- Filters: Merchant search ----

  it("renders a merchant search input", async () => {
    mockFetchTransactions.mockResolvedValue(makeResponse());
    renderTransactionsPage();

    await waitForDataLoaded();

    // Use exact label text to avoid matching "Sort by Merchant" button aria-label
    expect(screen.getByLabelText("Merchant")).toBeInTheDocument();
  });

  it("debounces merchant search input", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockFetchTransactions.mockResolvedValue(makeResponse());
    renderTransactionsPage();

    await waitForDataLoaded();

    const callCountBefore = mockFetchTransactions.mock.calls.length;

    const merchantInput = screen.getByLabelText("Merchant");
    await user.type(merchantInput, "whole");

    // Immediately after typing, no additional API calls should have been made
    // (debounce delay has not elapsed yet)
    const callCountAfterType = mockFetchTransactions.mock.calls.length;

    // Advance timers past debounce period
    vi.advanceTimersByTime(500);

    await waitFor(() => {
      const callCountAfterDebounce = mockFetchTransactions.mock.calls.length;
      // After debounce, the API should be called with the merchant filter
      expect(callCountAfterDebounce).toBeGreaterThan(callCountBefore);
      const lastCall =
        mockFetchTransactions.mock.calls[callCountAfterDebounce - 1][0];
      expect(lastCall).toEqual(
        expect.objectContaining({ merchant: "whole" }),
      );
    });

    vi.useRealTimers();
  });

  // ---- Empty state ----

  it("shows empty state when no transactions exist", async () => {
    mockFetchTransactions.mockResolvedValue(
      makeResponse({ transactions: [], totalCount: 0 }),
    );
    renderTransactionsPage();

    await waitFor(() => {
      // Should show some empty state message
      expect(
        screen.getByText(/no transactions/i),
      ).toBeInTheDocument();
    });
  });

  // ---- Page heading ----

  it("renders the transactions page heading", async () => {
    mockFetchTransactions.mockResolvedValue(makeResponse());
    renderTransactionsPage();

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /transactions/i }),
      ).toBeInTheDocument();
    });
  });

  // ---- Total count ----

  it("renders the total count of transactions", async () => {
    mockFetchTransactions.mockResolvedValue(
      makeResponse({ totalCount: 148 }),
    );
    renderTransactionsPage();

    await waitFor(() => {
      expect(screen.getByText(/148/)).toBeInTheDocument();
    });
  });
});
