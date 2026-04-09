/**
 * DashboardPage tests (frontend/src/pages/DashboardPage.tsx)
 *
 * Tests the dashboard page contract from SPEC.md Milestone 5:
 * - Renders stat cards with weekly total + % change, monthly total + % change, receipt count
 * - Top categories: up to 5, sorted by total descending, with amounts and percentages
 * - Recent activity: up to 5 receipts with merchant, amount, date
 * - Positive change = upward indicator, negative = downward, null = no indicator
 * - Loading state while fetching dashboard data
 * - Error state when fetch fails
 *
 * Spec references:
 * - SPEC.md >> Milestone 5 Acceptance Criteria
 * - api-contracts.md >> GET /api/dashboard/summary
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { DashboardSummary } from "@/api/dashboard";

// ---- Mocks ----

const mockFetchDashboardSummary = vi.fn();

vi.mock("@/api/dashboard", () => ({
  fetchDashboardSummary: (...args: unknown[]) =>
    mockFetchDashboardSummary(...args),
}));

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

import DashboardPage from "@/pages/DashboardPage";

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
}

function renderDashboard() {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/"]}>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function makeSummary(overrides: Partial<DashboardSummary> = {}): DashboardSummary {
  return {
    month: "2026-03",
    totalSpent: 2482.5,
    previousMonthTotal: 2210.75,
    monthlyChangePercent: 12.3,
    weeklySpent: 620.75,
    previousWeekTotal: 580.3,
    weeklyChangePercent: 7.0,
    receiptCount: 48,
    confirmedCount: 45,
    processingCount: 2,
    failedCount: 1,
    topCategories: [
      {
        category: "groceries-food",
        categoryDisplay: "Groceries & Food",
        total: 890.25,
        percent: 35.9,
      },
      {
        category: "dining",
        categoryDisplay: "Dining",
        total: 450.0,
        percent: 18.1,
      },
    ],
    recentActivity: [
      {
        receiptId: "01HQ3K5P7M2N4R6S8T0V",
        merchant: "Whole Foods Market",
        total: 30.39,
        category: "groceries-food",
        categoryDisplay: "Groceries & Food",
        receiptDate: "2026-03-25",
        status: "confirmed",
      },
      {
        receiptId: "01HQ3K5P7M2N4R6S8T0W",
        merchant: "Starbucks",
        total: 5.75,
        category: "dining",
        categoryDisplay: "Dining",
        receiptDate: "2026-03-24",
        status: "confirmed",
      },
    ],
    ...overrides,
  };
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ---- Loading state ----

  it("shows a loading indicator while fetching dashboard data", () => {
    mockFetchDashboardSummary.mockReturnValue(new Promise(() => {}));
    renderDashboard();

    const status = screen.queryByRole("status");
    const spinner = document.querySelector("[class*=animate-spin]");
    expect(
      status || spinner,
    ).toBeTruthy();
  });

  // ---- Error state ----

  it("shows error state when dashboard fetch fails", async () => {
    mockFetchDashboardSummary.mockRejectedValue(new Error("Network error"));
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/error|failed/i)).toBeInTheDocument();
    });
  });

  // ---- Monthly total stat card ----

  it("renders the monthly total spent value", async () => {
    mockFetchDashboardSummary.mockResolvedValue(
      makeSummary({ totalSpent: 2482.5 }),
    );
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("$2,482.50")).toBeInTheDocument();
    });
  });

  // ---- Weekly total stat card ----

  it("renders the weekly total spent value", async () => {
    mockFetchDashboardSummary.mockResolvedValue(
      makeSummary({ weeklySpent: 620.75 }),
    );
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("$620.75")).toBeInTheDocument();
    });
  });

  // ---- Receipt count ----

  it("renders the receipt count", async () => {
    mockFetchDashboardSummary.mockResolvedValue(
      makeSummary({ receiptCount: 48 }),
    );
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("48")).toBeInTheDocument();
    });
  });

  // ---- Change percent indicators ----

  it("shows positive change indicator for spending increase", async () => {
    mockFetchDashboardSummary.mockResolvedValue(
      makeSummary({ monthlyChangePercent: 12.3 }),
    );
    renderDashboard();

    await waitFor(() => {
      // Should show "12.3%" with an increase indicator
      expect(screen.getByText("12.3%")).toBeInTheDocument();
    });

    // Per SPEC: positive = spending increase. The aria-label indicates "increase".
    const increaseIndicator = screen.getByLabelText(/12\.3%.*increase/i);
    expect(increaseIndicator).toBeInTheDocument();
  });

  it("shows negative change indicator for spending decrease", async () => {
    mockFetchDashboardSummary.mockResolvedValue(
      makeSummary({ monthlyChangePercent: -8.5 }),
    );
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("8.5%")).toBeInTheDocument();
    });

    const decreaseIndicator = screen.getByLabelText(/8\.5%.*decrease/i);
    expect(decreaseIndicator).toBeInTheDocument();
  });

  it("does not show any change indicator when change percent is null", async () => {
    mockFetchDashboardSummary.mockResolvedValue(
      makeSummary({
        monthlyChangePercent: null,
        weeklyChangePercent: null,
        previousMonthTotal: null,
        previousWeekTotal: null,
      }),
    );
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("$2,482.50")).toBeInTheDocument();
    });

    // No increase or decrease indicators
    expect(screen.queryByLabelText(/increase/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/decrease/i)).not.toBeInTheDocument();
  });

  // ---- Top categories ----

  it("renders top categories with display names", async () => {
    mockFetchDashboardSummary.mockResolvedValue(makeSummary());
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("Groceries & Food")).toBeInTheDocument();
    });
    expect(screen.getByText("Dining")).toBeInTheDocument();
  });

  it("renders top categories heading", async () => {
    mockFetchDashboardSummary.mockResolvedValue(makeSummary());
    renderDashboard();

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /top categories/i }),
      ).toBeInTheDocument();
    });
  });

  it("renders up to 5 top categories", async () => {
    const fiveCategories = [
      { category: "a", categoryDisplay: "Cat A", total: 500, percent: 30 },
      { category: "b", categoryDisplay: "Cat B", total: 400, percent: 24 },
      { category: "c", categoryDisplay: "Cat C", total: 300, percent: 18 },
      { category: "d", categoryDisplay: "Cat D", total: 200, percent: 12 },
      { category: "e", categoryDisplay: "Cat E", total: 100, percent: 6 },
    ];
    mockFetchDashboardSummary.mockResolvedValue(
      makeSummary({ topCategories: fiveCategories }),
    );
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("Cat A")).toBeInTheDocument();
    });
    expect(screen.getByText("Cat B")).toBeInTheDocument();
    expect(screen.getByText("Cat C")).toBeInTheDocument();
    expect(screen.getByText("Cat D")).toBeInTheDocument();
    expect(screen.getByText("Cat E")).toBeInTheDocument();
  });

  it("renders category amounts", async () => {
    mockFetchDashboardSummary.mockResolvedValue(
      makeSummary({
        topCategories: [
          {
            category: "groceries-food",
            categoryDisplay: "Groceries & Food",
            total: 890.25,
            percent: 35.9,
          },
        ],
      }),
    );
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("$890.25")).toBeInTheDocument();
    });
  });

  it("renders category percentages via progressbar", async () => {
    mockFetchDashboardSummary.mockResolvedValue(
      makeSummary({
        topCategories: [
          {
            category: "groceries-food",
            categoryDisplay: "Groceries & Food",
            total: 890.25,
            percent: 35.9,
          },
        ],
      }),
    );
    renderDashboard();

    await waitFor(() => {
      // The percentage is displayed as an aria-label on the progressbar
      const progressbar = screen.getByRole("progressbar", {
        name: /35\.9%/,
      });
      expect(progressbar).toBeInTheDocument();
    });
  });

  it("shows a message when there are no categories", async () => {
    mockFetchDashboardSummary.mockResolvedValue(
      makeSummary({ topCategories: [] }),
    );
    renderDashboard();

    await waitFor(() => {
      expect(
        screen.getByText(/no category data/i),
      ).toBeInTheDocument();
    });
  });

  // ---- Recent activity ----

  it("renders recent activity with merchant names", async () => {
    mockFetchDashboardSummary.mockResolvedValue(makeSummary());
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("Whole Foods Market")).toBeInTheDocument();
    });
    expect(screen.getByText("Starbucks")).toBeInTheDocument();
  });

  it("renders recent activity heading", async () => {
    mockFetchDashboardSummary.mockResolvedValue(makeSummary());
    renderDashboard();

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /recent activity/i }),
      ).toBeInTheDocument();
    });
  });

  it("renders recent activity amounts", async () => {
    mockFetchDashboardSummary.mockResolvedValue(makeSummary());
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("$30.39")).toBeInTheDocument();
    });
    expect(screen.getByText("$5.75")).toBeInTheDocument();
  });

  it("shows a message when there are no recent receipts", async () => {
    mockFetchDashboardSummary.mockResolvedValue(
      makeSummary({ recentActivity: [] }),
    );
    renderDashboard();

    await waitFor(() => {
      expect(
        screen.getByText(/no recent receipts/i),
      ).toBeInTheDocument();
    });
  });

  // ---- Stat card labels ----

  it("renders stat card labels for weekly and monthly spending", async () => {
    mockFetchDashboardSummary.mockResolvedValue(makeSummary());
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/weekly/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/monthly/i)).toBeInTheDocument();
  });

  // ---- Weekly change indicator ----

  it("shows weekly change indicator when weekly change is provided", async () => {
    mockFetchDashboardSummary.mockResolvedValue(
      makeSummary({ weeklyChangePercent: 7.0 }),
    );
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("7.0%")).toBeInTheDocument();
    });
  });

  // ---- Zero spending ----

  it("renders $0.00 for zero spending", async () => {
    mockFetchDashboardSummary.mockResolvedValue(
      makeSummary({
        totalSpent: 0,
        weeklySpent: 0,
        receiptCount: 1,
        confirmedCount: 1,
        processingCount: 0,
        failedCount: 0,
        monthlyChangePercent: null,
        weeklyChangePercent: null,
        previousMonthTotal: null,
        previousWeekTotal: null,
        topCategories: [],
        recentActivity: [],
      }),
    );
    renderDashboard();

    await waitFor(() => {
      // Should render zero amounts
      const zeroElements = screen.getAllByText("$0.00");
      expect(zeroElements.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows welcome empty state when there are no receipts", async () => {
    mockFetchDashboardSummary.mockResolvedValue(
      makeSummary({
        receiptCount: 0,
        confirmedCount: 0,
        processingCount: 0,
        failedCount: 0,
        topCategories: [],
        recentActivity: [],
      }),
    );
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/welcome to novascan/i)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /scan your first receipt/i })).toBeInTheDocument();
    });
  });

  // ---- Dashboard page heading ----

  it("renders the dashboard page with a heading", async () => {
    mockFetchDashboardSummary.mockResolvedValue(makeSummary());
    renderDashboard();

    await waitFor(() => {
      // Dashboard should have a heading
      const heading = screen.getByRole("heading", { level: 1 });
      expect(heading).toBeInTheDocument();
    });
  });
});
