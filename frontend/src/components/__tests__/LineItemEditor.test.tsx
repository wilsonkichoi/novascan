/**
 * LineItemEditor tests (frontend/src/components/LineItemEditor.tsx)
 *
 * Tests the line item editing contract from SPEC.md Milestone 4:
 * - Renders line items in read mode by default (not editing)
 * - Inline editing: edit name, quantity, price fields
 * - Add new line items
 * - Remove existing line items (two-step confirm)
 * - Save calls onSave with properly formatted data
 * - Cancel reverts to original line items
 * - Validation errors shown for invalid input
 * - Shows saving state when isSaving is true
 * - Shows save error message when saveError is set (in editing mode)
 *
 * Spec references:
 * - SPEC.md >> Milestone 4: Line item editing
 * - api-contracts.md >> PUT /api/receipts/{id}/items
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReceiptDetailLineItem } from "@/api/receipts";

// Mock categories hook used inside some implementations
vi.mock("@/hooks/useCategories", () => ({
  useCategories: vi.fn().mockReturnValue({
    data: { categories: [] },
    isLoading: false,
  }),
  useCreateCategory: vi.fn().mockReturnValue({
    mutateAsync: vi.fn(),
    isPending: false,
    error: null,
  }),
  useDeleteCategory: vi.fn().mockReturnValue({
    mutateAsync: vi.fn(),
    isPending: false,
    error: null,
  }),
  usePipelineResults: vi.fn().mockReturnValue({
    data: null,
    isLoading: false,
    error: null,
  }),
}));

vi.mock("@/api/categories", () => ({
  fetchCategories: vi.fn().mockResolvedValue({ categories: [] }),
  createCategory: vi.fn(),
  deleteCategory: vi.fn(),
  fetchPipelineResults: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  getValidIdToken: vi.fn().mockResolvedValue("mock-token"),
}));

import LineItemEditor from "@/components/LineItemEditor";

function makeLineItems(): ReceiptDetailLineItem[] {
  return [
    {
      sortOrder: 1,
      name: "Organic Whole Milk",
      quantity: 2,
      unitPrice: 4.99,
      totalPrice: 9.98,
      subcategory: "dairy-cheese-eggs",
      subcategoryDisplay: "Dairy, Cheese & Eggs",
    },
    {
      sortOrder: 2,
      name: "Avocado (Bag of 5)",
      quantity: 1,
      unitPrice: 6.50,
      totalPrice: 6.50,
      subcategory: "produce",
      subcategoryDisplay: "Produce",
    },
  ];
}

const defaultProps = {
  lineItems: makeLineItems(),
  onSave: vi.fn(),
  onSaveSuccess: vi.fn(),
  isSaving: false,
  saveError: null,
};

function renderEditor(props: Partial<typeof defaultProps> = {}) {
  return render(<LineItemEditor {...defaultProps} {...props} />);
}

describe("LineItemEditor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ---- Read mode rendering ----

  it("renders line item names in read mode", () => {
    renderEditor();
    expect(screen.getByText("Organic Whole Milk")).toBeInTheDocument();
    expect(screen.getByText("Avocado (Bag of 5)")).toBeInTheDocument();
  });

  it("renders line item unit prices in read mode", () => {
    renderEditor();
    // unitPrice $4.99 for item 1 is unique (totalPrice is $9.98)
    expect(screen.getByText("$4.99")).toBeInTheDocument();
  });

  it("renders line item total prices in read mode", () => {
    renderEditor();
    // totalPrice $9.98 for item 1 is unique
    expect(screen.getByText("$9.98")).toBeInTheDocument();
  });

  it("shows an edit button to enter editing mode", () => {
    renderEditor();
    expect(
      screen.getByRole("button", { name: /edit/i }),
    ).toBeInTheDocument();
  });

  it("renders empty state when no line items", () => {
    renderEditor({ lineItems: [] });
    // Should not crash and should still show the edit button
    expect(
      screen.getByRole("button", { name: /edit/i }),
    ).toBeInTheDocument();
  });

  // ---- Enter editing mode ----

  it("enters editing mode when edit button is clicked", async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByRole("button", { name: /edit/i }));

    // In edit mode, should show input fields
    await waitFor(() => {
      const inputs = screen.getAllByRole("textbox");
      expect(inputs.length).toBeGreaterThan(0);
    });
  });

  it("shows save and cancel buttons in editing mode", async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByRole("button", { name: /edit/i }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /save/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /cancel/i }),
      ).toBeInTheDocument();
    });
  });

  // ---- Inline editing ----

  it("allows editing a line item name", async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByRole("button", { name: /edit/i }));

    await waitFor(() => {
      expect(screen.getByDisplayValue("Organic Whole Milk")).toBeInTheDocument();
    });

    const nameInput = screen.getByDisplayValue("Organic Whole Milk");
    await user.clear(nameInput);
    await user.type(nameInput, "Regular Whole Milk");

    expect(screen.getByDisplayValue("Regular Whole Milk")).toBeInTheDocument();
  });

  it("allows editing a line item quantity", async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByRole("button", { name: /edit/i }));

    await waitFor(() => {
      // Quantity of first item is "2"
      expect(screen.getByDisplayValue("2")).toBeInTheDocument();
    });

    const qtyInput = screen.getByDisplayValue("2");
    await user.clear(qtyInput);
    await user.type(qtyInput, "5");

    expect(screen.getByDisplayValue("5")).toBeInTheDocument();
  });

  it("allows editing a line item unit price", async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByRole("button", { name: /edit/i }));

    await waitFor(() => {
      // unitPrice "4.99" is unique for item 1 (totalPrice is "9.98")
      expect(screen.getByDisplayValue("4.99")).toBeInTheDocument();
    });

    const priceInput = screen.getByDisplayValue("4.99");
    await user.clear(priceInput);
    await user.type(priceInput, "7.49");

    expect(screen.getByDisplayValue("7.49")).toBeInTheDocument();
  });

  // ---- Add line item ----

  it("shows an add button in editing mode", async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByRole("button", { name: /edit/i }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /add/i }),
      ).toBeInTheDocument();
    });
  });

  it("adds a new empty row when add button is clicked", async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByRole("button", { name: /edit/i }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /add/i }),
      ).toBeInTheDocument();
    });

    const initialInputCount = screen.getAllByRole("textbox").length;
    await user.click(screen.getByRole("button", { name: /add/i }));

    await waitFor(() => {
      expect(screen.getAllByRole("textbox").length).toBeGreaterThan(
        initialInputCount,
      );
    });
  });

  // ---- Remove line item (two-step confirm) ----

  it("shows remove buttons for each line item in editing mode", async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByRole("button", { name: /edit/i }));

    await waitFor(() => {
      // Each line item has a "Remove item N" button
      expect(
        screen.getByRole("button", { name: /remove item 1/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /remove item 2/i }),
      ).toBeInTheDocument();
    });
  });

  it("removes a line item after two-step confirmation", async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByRole("button", { name: /edit/i }));

    await waitFor(() => {
      expect(screen.getByDisplayValue("Organic Whole Milk")).toBeInTheDocument();
    });

    // Step 1: Click remove button
    await user.click(
      screen.getByRole("button", { name: /remove item 1/i }),
    );

    // Step 2: Confirm remove
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /confirm remove item 1/i }),
      ).toBeInTheDocument();
    });

    await user.click(
      screen.getByRole("button", { name: /confirm remove item 1/i }),
    );

    // The item should be removed
    await waitFor(() => {
      expect(
        screen.queryByDisplayValue("Organic Whole Milk"),
      ).not.toBeInTheDocument();
    });
  });

  // ---- Save ----

  it("calls onSave with formatted items when save is clicked", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    renderEditor({ onSave });

    await user.click(screen.getByRole("button", { name: /edit/i }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /save/i }),
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledTimes(1);
    });

    // onSave should be called with an array of items
    const savedItems = onSave.mock.calls[0][0];
    expect(Array.isArray(savedItems)).toBe(true);
    expect(savedItems.length).toBe(2);
    expect(savedItems[0]).toEqual(
      expect.objectContaining({
        name: "Organic Whole Milk",
        quantity: 2,
        unitPrice: 4.99,
        totalPrice: 9.98,
      }),
    );
  });

  it("calls onSave with numeric values (not strings) for price and quantity", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    renderEditor({ onSave });

    await user.click(screen.getByRole("button", { name: /edit/i }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /save/i }),
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalled();
    });

    const savedItems = onSave.mock.calls[0][0];
    expect(typeof savedItems[0].quantity).toBe("number");
    expect(typeof savedItems[0].unitPrice).toBe("number");
    expect(typeof savedItems[0].totalPrice).toBe("number");
  });

  // ---- Cancel ----

  it("reverts to original items when cancel is clicked", async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByRole("button", { name: /edit/i }));

    await waitFor(() => {
      expect(screen.getByDisplayValue("Organic Whole Milk")).toBeInTheDocument();
    });

    // Modify a name
    const nameInput = screen.getByDisplayValue("Organic Whole Milk");
    await user.clear(nameInput);
    await user.type(nameInput, "Changed Name");

    expect(screen.getByDisplayValue("Changed Name")).toBeInTheDocument();

    // Click cancel
    await user.click(screen.getByRole("button", { name: /cancel/i }));

    // Should revert to original data shown in read mode
    await waitFor(() => {
      expect(screen.getByText("Organic Whole Milk")).toBeInTheDocument();
    });
    expect(screen.queryByDisplayValue("Changed Name")).not.toBeInTheDocument();
  });

  it("does not call onSave when cancel is clicked", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    renderEditor({ onSave });

    await user.click(screen.getByRole("button", { name: /edit/i }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /cancel/i }),
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /cancel/i }));

    expect(onSave).not.toHaveBeenCalled();
  });

  // ---- Validation errors ----

  it("shows validation error for empty item name on save", async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByRole("button", { name: /edit/i }));

    await waitFor(() => {
      expect(screen.getByDisplayValue("Organic Whole Milk")).toBeInTheDocument();
    });

    // Clear the name field
    const nameInput = screen.getByDisplayValue("Organic Whole Milk");
    await user.clear(nameInput);

    // Try to save
    await user.click(screen.getByRole("button", { name: /save/i }));

    // Should show a validation error: "Name is required"
    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    });
  });

  it("shows validation error for quantity of 0", async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByRole("button", { name: /edit/i }));

    await waitFor(() => {
      // Item 1 has quantity "2"
      expect(screen.getByDisplayValue("2")).toBeInTheDocument();
    });

    // Set quantity to 0
    const qtyInput = screen.getByDisplayValue("2");
    await user.clear(qtyInput);
    await user.type(qtyInput, "0");

    // Try to save
    await user.click(screen.getByRole("button", { name: /save/i }));

    // Should show a validation error: "Must be greater than 0"
    await waitFor(() => {
      expect(screen.getByText(/must be greater than 0/i)).toBeInTheDocument();
    });
  });

  it("shows validation error for negative unit price", async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByRole("button", { name: /edit/i }));

    await waitFor(() => {
      // unitPrice "4.99" is unique for item 1
      expect(screen.getByDisplayValue("4.99")).toBeInTheDocument();
    });

    const priceInput = screen.getByDisplayValue("4.99");
    await user.clear(priceInput);
    await user.type(priceInput, "-1");

    // Try to save
    await user.click(screen.getByRole("button", { name: /save/i }));

    // Should show a validation error: "Must be 0 or greater"
    await waitFor(() => {
      expect(screen.getByText(/must be 0 or greater/i)).toBeInTheDocument();
    });
  });

  // ---- Save error ----

  it("displays save error message when in editing mode", async () => {
    const user = userEvent.setup();
    const { rerender } = renderEditor();

    // Enter editing mode
    await user.click(screen.getByRole("button", { name: /edit/i }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /save/i }),
      ).toBeInTheDocument();
    });

    // Rerender with saveError
    rerender(
      <LineItemEditor
        {...defaultProps}
        saveError="Failed to update items"
      />,
    );

    // The error message should now be visible (uses role="alert")
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Failed to update items",
      );
    });
  });

  // ---- sortOrder in saved data ----

  it("includes sortOrder in saved items, in ascending order", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    renderEditor({ onSave });

    await user.click(screen.getByRole("button", { name: /edit/i }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /save/i }),
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalled();
    });

    const savedItems = onSave.mock.calls[0][0];
    expect(savedItems[0]).toHaveProperty("sortOrder");
    expect(savedItems[1]).toHaveProperty("sortOrder");
    expect(savedItems[0].sortOrder).toBeLessThan(savedItems[1].sortOrder);
  });
});
