/**
 * TransactionFilters tests (frontend/src/components/TransactionFilters.tsx)
 *
 * Tests the transaction filters component contract from SPEC.md Milestone 5:
 * - Date range filter: start date and end date pickers
 * - Category filter: dropdown with predefined categories
 * - Status filter: processing/confirmed/failed
 * - Merchant search: text input with debounced API call
 *
 * Spec references:
 * - SPEC.md >> Milestone 5 Acceptance Criteria
 * - api-contracts.md >> GET /api/transactions query parameters
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TransactionFilters, {
  type FilterValues,
} from "@/components/TransactionFilters";

const defaultValues: FilterValues = {
  startDate: "",
  endDate: "",
  category: "",
  status: "",
  merchant: "",
};

function renderFilters(
  values = defaultValues,
  onChange = vi.fn(),
) {
  return render(
    <TransactionFilters values={values} onChange={onChange} />,
  );
}

describe("TransactionFilters", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ---- Date range inputs ----

  it("renders start date input", () => {
    renderFilters();

    expect(screen.getByLabelText(/start date/i)).toBeInTheDocument();
  });

  it("renders end date input", () => {
    renderFilters();

    expect(screen.getByLabelText(/end date/i)).toBeInTheDocument();
  });

  it("start date and end date are date inputs", () => {
    renderFilters();

    const startDate = screen.getByLabelText(/start date/i);
    const endDate = screen.getByLabelText(/end date/i);
    expect(startDate).toHaveAttribute("type", "date");
    expect(endDate).toHaveAttribute("type", "date");
  });

  it("calls onChange when start date is changed", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderFilters(defaultValues, onChange);

    const startDate = screen.getByLabelText(/start date/i);
    await user.clear(startDate);
    await user.type(startDate, "2026-03-01");

    await waitFor(() => {
      expect(onChange).toHaveBeenCalledWith(
        expect.objectContaining({ startDate: "2026-03-01" }),
      );
    });
  });

  it("calls onChange when end date is changed", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderFilters(defaultValues, onChange);

    const endDate = screen.getByLabelText(/end date/i);
    await user.clear(endDate);
    await user.type(endDate, "2026-03-31");

    await waitFor(() => {
      expect(onChange).toHaveBeenCalledWith(
        expect.objectContaining({ endDate: "2026-03-31" }),
      );
    });
  });

  // ---- Category dropdown ----

  it("renders a category filter with 'All categories' option", () => {
    renderFilters();

    const categorySelect = screen.getByLabelText(/category/i);
    expect(categorySelect).toBeInTheDocument();

    // Should have "All categories" as the default option
    const options = categorySelect.querySelectorAll("option");
    const allOption = Array.from(options).find(
      (opt) => opt.textContent === "All categories",
    );
    expect(allOption).toBeTruthy();
  });

  it("renders predefined category options", () => {
    renderFilters();

    const categorySelect = screen.getByLabelText(/category/i);
    const options = categorySelect.querySelectorAll("option");
    const optionTexts = Array.from(options).map((opt) => opt.textContent);

    // Should have at least the 13 predefined categories plus "All categories"
    expect(options.length).toBeGreaterThanOrEqual(14);

    // Spot-check a few categories per SPEC
    expect(optionTexts).toContain("Groceries & Food");
    expect(optionTexts).toContain("Dining");
    expect(optionTexts).toContain("Other");
  });

  it("calls onChange when category is selected", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderFilters(defaultValues, onChange);

    const categorySelect = screen.getByLabelText(/category/i);
    await user.selectOptions(categorySelect, "dining");

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ category: "dining" }),
    );
  });

  // ---- Status dropdown ----

  it("renders a status filter with all status options", () => {
    renderFilters();

    const statusSelect = screen.getByLabelText(/status/i);
    expect(statusSelect).toBeInTheDocument();

    const options = statusSelect.querySelectorAll("option");
    const optionTexts = Array.from(options).map((opt) =>
      opt.textContent?.toLowerCase(),
    );

    expect(optionTexts).toContain("all statuses");
    expect(optionTexts).toContain("confirmed");
    expect(optionTexts).toContain("processing");
    expect(optionTexts).toContain("failed");
  });

  it("calls onChange when status is selected", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderFilters(defaultValues, onChange);

    const statusSelect = screen.getByLabelText(/status/i);
    await user.selectOptions(statusSelect, "confirmed");

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ status: "confirmed" }),
    );
  });

  // ---- Merchant search ----

  it("renders a merchant search input", () => {
    renderFilters();

    expect(screen.getByLabelText(/merchant/i)).toBeInTheDocument();
  });

  it("debounces merchant search input before calling onChange", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const onChange = vi.fn();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    renderFilters(defaultValues, onChange);

    const merchantInput = screen.getByLabelText(/merchant/i);
    await user.type(merchantInput, "who");

    // onChange should not have been called with merchant during typing
    // (only date/category/status changes trigger immediately)
    const merchantCalls = onChange.mock.calls.filter(
      (call) => call[0].merchant === "who",
    );
    expect(merchantCalls.length).toBe(0);

    // After debounce period
    vi.advanceTimersByTime(500);

    await waitFor(() => {
      expect(onChange).toHaveBeenCalledWith(
        expect.objectContaining({ merchant: "who" }),
      );
    });

    vi.useRealTimers();
  });

  // ---- Filter values reflect external state ----

  it("reflects external filter values in inputs", () => {
    const values: FilterValues = {
      startDate: "2026-01-01",
      endDate: "2026-03-31",
      category: "dining",
      status: "confirmed",
      merchant: "test",
    };
    renderFilters(values);

    expect(screen.getByLabelText(/start date/i)).toHaveValue("2026-01-01");
    expect(screen.getByLabelText(/end date/i)).toHaveValue("2026-03-31");
    expect(screen.getByLabelText(/category/i)).toHaveValue("dining");
    expect(screen.getByLabelText(/status/i)).toHaveValue("confirmed");
    // Merchant might be debounced but should reflect initial value
    expect(screen.getByLabelText(/merchant/i)).toHaveValue("test");
  });

  // ---- Reset to "All" ----

  it("resetting category to empty string selects 'All categories'", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    const values: FilterValues = {
      ...defaultValues,
      category: "dining",
    };
    renderFilters(values, onChange);

    const categorySelect = screen.getByLabelText(/category/i);
    await user.selectOptions(categorySelect, "");

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ category: "" }),
    );
  });
});
