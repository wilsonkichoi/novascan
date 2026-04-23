/**
 * ReceiptDetailPage tests (frontend/src/pages/ReceiptDetailPage.tsx)
 *
 * Tests the receipt detail page contract from SPEC.md Milestone 4:
 * - Renders receipt data (merchant, total, date, category, status, payment method)
 * - Displays receipt image alongside extracted data
 * - Shows correct status badges: Processing, Confirmed, Failed
 * - Shows loading state while fetching receipt
 * - Shows 404/not-found state when receipt does not exist
 * - Shows delete button with confirmation dialog
 * - Back navigation link to receipts list
 * - Pipeline comparison toggle visibility by role
 *
 * Spec references:
 * - SPEC.md >> Milestone 4 Acceptance Criteria
 * - api-contracts.md >> GET /api/receipts/{id}
 * - api-contracts.md >> DELETE /api/receipts/{id}
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReceiptDetail } from "@/api/receipts";

// ---- Mocks ----

const mockGetReceipt = vi.fn();
const mockDeleteReceipt = vi.fn();
const mockUpdateReceipt = vi.fn();
const mockUpdateItems = vi.fn();

vi.mock("@/api/receipts", async () => {
  const actual = await vi.importActual<typeof import("@/api/receipts")>(
    "@/api/receipts",
  );
  return {
    ...actual,
    getReceipt: (...args: unknown[]) => mockGetReceipt(...args),
    deleteReceipt: (...args: unknown[]) => mockDeleteReceipt(...args),
    updateReceipt: (...args: unknown[]) => mockUpdateReceipt(...args),
    updateItems: (...args: unknown[]) => mockUpdateItems(...args),
  };
});

const mockFetchCategories = vi.fn();
const mockCreateCategory = vi.fn();
const mockDeleteCategory = vi.fn();
const mockFetchPipelineResults = vi.fn();

vi.mock("@/api/categories", () => ({
  fetchCategories: (...args: unknown[]) => mockFetchCategories(...args),
  createCategory: (...args: unknown[]) => mockCreateCategory(...args),
  deleteCategory: (...args: unknown[]) => mockDeleteCategory(...args),
  fetchPipelineResults: (...args: unknown[]) =>
    mockFetchPipelineResults(...args),
}));

vi.mock("@/lib/auth", () => ({
  getValidIdToken: vi.fn().mockResolvedValue("mock-token"),
  initiateAuth: vi.fn(),
  respondToChallenge: vi.fn(),
  refreshTokens: vi.fn().mockResolvedValue(null),
  signOut: vi.fn(),
}));

// Mock useAuth to control user roles for staff/non-staff tests
const mockUseAuth = vi.fn();
vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => mockUseAuth(),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import ReceiptDetailPage from "@/pages/ReceiptDetailPage";

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

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

function renderDetailPage(receiptId = "01HQ3K5P7M2N4R6S8T0V") {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/receipts/${receiptId}`]}>
        <Routes>
          <Route path="/receipts/:id" element={<ReceiptDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function makeReceiptDetail(
  overrides: Partial<ReceiptDetail> = {},
): ReceiptDetail {
  return {
    receiptId: "01HQ3K5P7M2N4R6S8T0V",
    receiptDate: "2026-03-25",
    merchant: "Whole Foods Market",
    merchantAddress: "123 Main St, Austin, TX 78701",
    total: 30.39,
    subtotal: 28.14,
    tax: 2.25,
    tip: null,
    category: "groceries-food",
    categoryDisplay: "Groceries & Food",
    subcategory: "supermarket-grocery",
    subcategoryDisplay: "Supermarket / Grocery",
    status: "confirmed",
    usedFallback: false,
    rankingWinner: "ocr-ai",
    imageUrl: "https://example.com/receipt.jpg",
    paymentMethod: "VISA *1234",
    lineItems: [
      {
        sortOrder: 1,
        name: "Organic Whole Milk",
        quantity: 1,
        unitPrice: 5.99,
        totalPrice: 5.99,
        subcategory: "dairy-cheese-eggs",
        subcategoryDisplay: "Dairy, Cheese & Eggs",
      },
      {
        sortOrder: 2,
        name: "Avocado (Bag of 5)",
        quantity: 1,
        unitPrice: 6.5,
        totalPrice: 6.5,
        subcategory: "produce",
        subcategoryDisplay: "Produce",
      },
    ],
    createdAt: "2026-03-25T14:30:00Z",
    updatedAt: "2026-03-25T14:31:00Z",
    ...overrides,
  };
}

/** Helper: wait for receipt data to be rendered (uses heading which is unique). */
async function waitForReceiptLoaded(merchantName = "Whole Foods Market") {
  await waitFor(() => {
    expect(
      screen.getByRole("heading", { name: merchantName }),
    ).toBeInTheDocument();
  });
}

describe("ReceiptDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      user: { userId: "user-123", email: "user@example.com", roles: ["user"] },
      isLoading: false,
      signIn: vi.fn(),
      verifyOtp: vi.fn(),
      signOut: vi.fn(),
    });
    mockFetchCategories.mockResolvedValue({
      categories: [
        {
          slug: "groceries-food",
          displayName: "Groceries & Food",
          isCustom: false,
          subcategories: [],
        },
      ],
    });
  });

  // ---- Loading state ----

  it("shows a loading indicator while fetching receipt data", () => {
    mockGetReceipt.mockReturnValue(new Promise(() => {}));
    renderDetailPage();

    // Should show some kind of loading indicator (spinner, status role, etc.)
    const status = screen.queryByRole("status");
    const spinner = document.querySelector("[class*=animate-spin]");
    expect(status || spinner).toBeTruthy();
  });

  // ---- Receipt data rendering ----

  it("renders the merchant name in a heading", async () => {
    mockGetReceipt.mockResolvedValue(
      makeReceiptDetail({ merchant: "Trader Joe's" }),
    );
    renderDetailPage();

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Trader Joe's" }),
      ).toBeInTheDocument();
    });
  });

  it("renders the formatted total amount", async () => {
    mockGetReceipt.mockResolvedValue(makeReceiptDetail({ total: 42.50 }));
    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByText("$42.50")).toBeInTheDocument();
    });
  });

  it("renders the formatted receipt date", async () => {
    mockGetReceipt.mockResolvedValue(
      makeReceiptDetail({ receiptDate: "2026-03-25" }),
    );
    renderDetailPage();

    await waitForReceiptLoaded();

    // The date is formatted and displayed (may appear in header + details)
    // Accept various date formats: "Mar 25, 2026", "March 25, 2026", "Wed, March 25, 2026", etc.
    const dateElements = screen.getAllByText(/march.*25.*2026|mar.*25.*2026/i);
    expect(dateElements.length).toBeGreaterThan(0);
  });

  it("renders the category display name", async () => {
    mockGetReceipt.mockResolvedValue(
      makeReceiptDetail({ categoryDisplay: "Groceries & Food" }),
    );
    renderDetailPage();

    await waitForReceiptLoaded();

    // Category display name appears somewhere in the details
    expect(screen.getAllByText("Groceries & Food").length).toBeGreaterThan(0);
  });

  it("renders the merchant address", async () => {
    mockGetReceipt.mockResolvedValue(
      makeReceiptDetail({
        merchantAddress: "123 Main St, Austin, TX 78701",
      }),
    );
    renderDetailPage();

    await waitForReceiptLoaded();

    expect(
      screen.getByText("123 Main St, Austin, TX 78701"),
    ).toBeInTheDocument();
  });

  it("renders the payment method", async () => {
    mockGetReceipt.mockResolvedValue(
      makeReceiptDetail({ paymentMethod: "VISA *1234" }),
    );
    renderDetailPage();

    await waitForReceiptLoaded();

    expect(screen.getByText("VISA *1234")).toBeInTheDocument();
  });

  it("renders subtotal and tax", async () => {
    mockGetReceipt.mockResolvedValue(
      makeReceiptDetail({ subtotal: 28.14, tax: 2.25 }),
    );
    renderDetailPage();

    await waitForReceiptLoaded();

    expect(screen.getByText("$28.14")).toBeInTheDocument();
    expect(screen.getByText("$2.25")).toBeInTheDocument();
  });

  // ---- Receipt image display ----

  it("renders the receipt image", async () => {
    mockGetReceipt.mockResolvedValue(
      makeReceiptDetail({ imageUrl: "https://example.com/receipt.jpg" }),
    );
    renderDetailPage();

    await waitForReceiptLoaded();

    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "https://example.com/receipt.jpg");
  });

  it("handles missing image gracefully without crashing", async () => {
    mockGetReceipt.mockResolvedValue(
      makeReceiptDetail({ imageUrl: null }),
    );
    renderDetailPage();

    await waitForReceiptLoaded();

    // Should not crash when imageUrl is null
    // Image may show a placeholder or be absent -- either is acceptable
  });

  // ---- Status display ----

  it("shows confirmed status indicator for confirmed receipts", async () => {
    mockGetReceipt.mockResolvedValue(
      makeReceiptDetail({ status: "confirmed" }),
    );
    renderDetailPage();

    await waitForReceiptLoaded();

    expect(screen.getByText(/confirmed/i)).toBeInTheDocument();
  });

  it("shows processing status indicator for processing receipts", async () => {
    mockGetReceipt.mockResolvedValue(
      makeReceiptDetail({
        status: "processing",
        merchant: "Test Store",
        total: null,
      }),
    );
    renderDetailPage();

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Test Store" }),
      ).toBeInTheDocument();
    });

    expect(screen.getByText(/processing/i)).toBeInTheDocument();
  });

  it("shows failed status indicator for failed receipts", async () => {
    mockGetReceipt.mockResolvedValue(
      makeReceiptDetail({ status: "failed" }),
    );
    renderDetailPage();

    await waitForReceiptLoaded();

    expect(screen.getByText(/failed/i)).toBeInTheDocument();
  });

  // ---- Line items rendering ----

  it("renders line item names", async () => {
    mockGetReceipt.mockResolvedValue(makeReceiptDetail());
    renderDetailPage();

    await waitForReceiptLoaded();

    expect(screen.getByText("Organic Whole Milk")).toBeInTheDocument();
    expect(screen.getByText("Avocado (Bag of 5)")).toBeInTheDocument();
  });

  it("renders line item prices (unitPrice and totalPrice)", async () => {
    // Use items with different unitPrice and totalPrice to avoid multi-match
    mockGetReceipt.mockResolvedValue(
      makeReceiptDetail({
        lineItems: [
          {
            sortOrder: 1,
            name: "Test Item",
            quantity: 3,
            unitPrice: 2.50,
            totalPrice: 7.50,
            subcategory: null,
            subcategoryDisplay: null,
          },
        ],
      }),
    );
    renderDetailPage();

    await waitForReceiptLoaded();

    expect(screen.getByText("$2.50")).toBeInTheDocument();
    expect(screen.getAllByText("$7.50").length).toBeGreaterThan(0);
  });

  // ---- 404 / Not Found ----

  it("shows not-found state when receipt does not exist", async () => {
    const { NotFoundError } = await import("@/api/receipts");
    mockGetReceipt.mockRejectedValue(new NotFoundError("Receipt not found"));
    renderDetailPage();

    await waitFor(() => {
      const notFoundText = screen.queryByText(/not found/i);
      const doesNotExist = screen.queryByText(/does not exist/i);
      expect(notFoundText || doesNotExist).toBeTruthy();
    });
  });

  // ---- Error state ----

  it("shows error state when fetch fails with generic error", async () => {
    mockGetReceipt.mockRejectedValue(new Error("Network error"));
    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByText(/error|failed/i)).toBeInTheDocument();
    });
  });

  // ---- Delete receipt ----

  it("shows a delete button", async () => {
    mockGetReceipt.mockResolvedValue(makeReceiptDetail());
    renderDetailPage();

    await waitForReceiptLoaded();

    expect(
      screen.getByRole("button", { name: /delete/i }),
    ).toBeInTheDocument();
  });

  it("shows confirmation dialog when delete is clicked", async () => {
    const user = userEvent.setup();
    mockGetReceipt.mockResolvedValue(makeReceiptDetail());
    renderDetailPage();

    await waitForReceiptLoaded();

    await user.click(screen.getByRole("button", { name: /delete/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/are you sure.*delete|cannot be undone|permanently/i),
      ).toBeInTheDocument();
    });
  });

  it("calls delete API and navigates when deletion is confirmed", async () => {
    const user = userEvent.setup();
    mockGetReceipt.mockResolvedValue(makeReceiptDetail());
    mockDeleteReceipt.mockResolvedValue(undefined);
    renderDetailPage();

    await waitForReceiptLoaded();

    // Click the delete button (the first one with aria-label "Delete receipt")
    await user.click(screen.getByRole("button", { name: /delete/i }));

    // Wait for confirmation dialog
    await waitFor(() => {
      expect(
        screen.getByText(/are you sure.*delete|cannot be undone|permanently/i),
      ).toBeInTheDocument();
    });

    // In the dialog footer, there are Cancel and Delete buttons
    // Find all buttons with "Delete" text -- the confirmation is the one in the dialog
    const allDeleteButtons = screen
      .getAllByRole("button")
      .filter((btn) => btn.textContent?.trim() === "Delete");
    // The last one is the dialog confirm button
    const confirmButton = allDeleteButtons[allDeleteButtons.length - 1];
    await user.click(confirmButton);

    await waitFor(() => {
      expect(mockDeleteReceipt).toHaveBeenCalledWith(
        "01HQ3K5P7M2N4R6S8T0V",
      );
    });

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalled();
    });
  });

  // ---- Back navigation ----

  it("shows a back link to navigate to receipts list", async () => {
    mockGetReceipt.mockResolvedValue(makeReceiptDetail());
    renderDetailPage();

    await waitForReceiptLoaded();

    // Should have a link with aria-label "Back to receipts" or similar
    const backLink = screen.queryByRole("link", { name: /back/i });
    expect(backLink).toBeInTheDocument();
    expect(backLink).toHaveAttribute("href", "/receipts");
  });

  // ---- Pipeline comparison visibility (available to all users) ----

  it("shows pipeline comparison toggle for all users", async () => {
    mockGetReceipt.mockResolvedValue(makeReceiptDetail());
    renderDetailPage();

    await waitForReceiptLoaded();

    expect(
      screen.getByText(/pipeline comparison/i),
    ).toBeInTheDocument();
  });

  // ---- Pipeline source toggle ----

  it("shows pipeline source toggle with Final, OCR + AI, AI Vision, and AI Vision v2 options", async () => {
    mockGetReceipt.mockResolvedValue(makeReceiptDetail());
    renderDetailPage();

    await waitForReceiptLoaded();

    expect(screen.getByText("Final")).toBeInTheDocument();
    expect(screen.getByText(/OCR \+ AI/)).toBeInTheDocument();
    expect(screen.getByText("AI Vision")).toBeInTheDocument();
    expect(screen.getByText("AI Vision v2")).toBeInTheDocument();
  });
});
