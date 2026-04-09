/**
 * TransactionTable tests (frontend/src/components/TransactionTable.tsx)
 *
 * Tests the transaction table component contract from SPEC.md Milestone 5:
 * - Renders sortable table with columns: date, merchant, category, amount, status
 * - Column header click calls onSort with the correct field
 * - Renders transaction data correctly in rows
 * - TransactionCard renders data for mobile card view
 *
 * Spec references:
 * - SPEC.md >> Milestone 5 Acceptance Criteria
 * - api-contracts.md >> GET /api/transactions
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import type { Transaction } from "@/api/transactions";

import TransactionTable, {
  TransactionCard,
} from "@/components/TransactionTable";

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

const defaultProps = {
  transactions: [
    makeTransaction(),
    makeTransaction({
      receiptId: "02",
      merchant: "Starbucks",
      total: 5.75,
      category: "dining",
      categoryDisplay: "Dining",
      receiptDate: "2026-03-24",
      status: "confirmed",
    }),
  ],
  sortBy: "date" as const,
  sortOrder: "desc" as const,
  onSort: vi.fn(),
};

function renderTable(props = defaultProps) {
  return render(
    <MemoryRouter>
      <TransactionTable {...props} />
    </MemoryRouter>,
  );
}

describe("TransactionTable", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ---- Column rendering ----

  it("renders a table element", () => {
    renderTable();

    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("renders sort buttons for date, amount, and merchant columns", () => {
    renderTable();

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

  // ---- Data rendering ----

  it("renders merchant names in table rows", () => {
    renderTable();

    expect(screen.getByText("Whole Foods Market")).toBeInTheDocument();
    expect(screen.getByText("Starbucks")).toBeInTheDocument();
  });

  it("renders transaction amounts formatted as currency", () => {
    renderTable();

    expect(screen.getByText("$30.39")).toBeInTheDocument();
    expect(screen.getByText("$5.75")).toBeInTheDocument();
  });

  it("renders category display names", () => {
    renderTable();

    expect(screen.getByText("Groceries & Food")).toBeInTheDocument();
    expect(screen.getByText("Dining")).toBeInTheDocument();
  });

  it("renders transaction status", () => {
    renderTable({
      ...defaultProps,
      transactions: [
        makeTransaction({ status: "confirmed" }),
        makeTransaction({
          receiptId: "02",
          status: "processing",
          merchant: "Pending Store",
        }),
        makeTransaction({
          receiptId: "03",
          status: "failed",
          merchant: "Failed Store",
        }),
      ],
    });

    // Status text may appear in both merchant cell (as placeholder) and status badge
    const confirmedElements = screen.getAllByText(/confirmed/i);
    expect(confirmedElements.length).toBeGreaterThanOrEqual(1);
    const processingElements = screen.getAllByText(/processing/i);
    expect(processingElements.length).toBeGreaterThanOrEqual(1);
    const failedElements = screen.getAllByText(/failed/i);
    expect(failedElements.length).toBeGreaterThanOrEqual(1);
  });

  // ---- Sort interaction ----

  it("calls onSort with 'date' when date header is clicked", async () => {
    const onSort = vi.fn();
    const user = userEvent.setup();
    renderTable({ ...defaultProps, onSort });

    await user.click(
      screen.getByRole("button", { name: /sort by date/i }),
    );

    expect(onSort).toHaveBeenCalledWith("date");
  });

  it("calls onSort with 'amount' when amount header is clicked", async () => {
    const onSort = vi.fn();
    const user = userEvent.setup();
    renderTable({ ...defaultProps, onSort });

    await user.click(
      screen.getByRole("button", { name: /sort by amount/i }),
    );

    expect(onSort).toHaveBeenCalledWith("amount");
  });

  it("calls onSort with 'merchant' when merchant header is clicked", async () => {
    const onSort = vi.fn();
    const user = userEvent.setup();
    renderTable({ ...defaultProps, onSort });

    await user.click(
      screen.getByRole("button", { name: /sort by merchant/i }),
    );

    expect(onSort).toHaveBeenCalledWith("merchant");
  });

  // ---- Empty state ----

  it("renders an empty table when no transactions are provided", () => {
    renderTable({
      ...defaultProps,
      transactions: [],
    });

    const table = screen.getByRole("table");
    expect(table).toBeInTheDocument();
    // Should have headers but no data rows
    const rows = screen.getAllByRole("row");
    // Only the header row
    expect(rows.length).toBe(1);
  });

  // ---- Null fields for processing receipts ----

  it("handles null merchant and total for processing receipts", () => {
    renderTable({
      ...defaultProps,
      transactions: [
        makeTransaction({
          status: "processing",
          merchant: null,
          total: null,
          category: null,
          categoryDisplay: null,
          receiptDate: null,
        }),
      ],
    });

    // Should render without crashing
    expect(screen.getByRole("table")).toBeInTheDocument();
    const processingElements = screen.getAllByText(/processing/i);
    expect(processingElements.length).toBeGreaterThanOrEqual(1);
  });
});

describe("TransactionCard", () => {
  it("renders transaction data in card format", () => {
    render(
      <MemoryRouter>
        <TransactionCard transaction={makeTransaction()} />
      </MemoryRouter>,
    );

    expect(screen.getByText("Whole Foods Market")).toBeInTheDocument();
    expect(screen.getByText("$30.39")).toBeInTheDocument();
  });

  it("renders category display name", () => {
    render(
      <MemoryRouter>
        <TransactionCard
          transaction={makeTransaction({
            categoryDisplay: "Groceries & Food",
          })}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("Groceries & Food")).toBeInTheDocument();
  });

  it("renders status badge", () => {
    render(
      <MemoryRouter>
        <TransactionCard
          transaction={makeTransaction({ status: "confirmed" })}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText(/confirmed/i)).toBeInTheDocument();
  });

  it("handles null fields gracefully (processing receipt)", () => {
    render(
      <MemoryRouter>
        <TransactionCard
          transaction={makeTransaction({
            merchant: null,
            total: null,
            status: "processing",
          })}
        />
      </MemoryRouter>,
    );

    const processingElements = screen.getAllByText(/processing/i);
    expect(processingElements.length).toBeGreaterThanOrEqual(1);
  });
});
