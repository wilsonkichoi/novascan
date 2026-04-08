/**
 * CategoryPicker tests (frontend/src/components/CategoryPicker.tsx)
 *
 * Tests the category picker contract from SPEC.md Milestone 4:
 * - Shows predefined categories from taxonomy
 * - Shows custom categories alongside predefined ones
 * - Create modal works: enter name, submit creates custom category
 * - Delete custom category works (two-step confirm)
 * - Cannot delete predefined categories
 * - Selecting a category calls onSelect with the slug
 * - Shows loading state while categories are being fetched
 *
 * Spec references:
 * - SPEC.md >> Milestone 4: Category picker
 * - api-contracts.md >> GET /api/categories
 * - api-contracts.md >> POST /api/categories
 * - api-contracts.md >> DELETE /api/categories/{slug}
 * - category-taxonomy.md >> Predefined Categories
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { CategoryItem } from "@/api/categories";

// ---- Mocks ----

const mockFetchCategories = vi.fn();
const mockCreateCategory = vi.fn();
const mockDeleteCategory = vi.fn();

vi.mock("@/api/categories", () => ({
  fetchCategories: (...args: unknown[]) => mockFetchCategories(...args),
  createCategory: (...args: unknown[]) => mockCreateCategory(...args),
  deleteCategory: (...args: unknown[]) => mockDeleteCategory(...args),
  fetchPipelineResults: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  getValidIdToken: vi.fn().mockResolvedValue("mock-token"),
}));

import CategoryPicker from "@/components/CategoryPicker";

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

function renderPicker(props: { value?: string | null; onSelect?: () => void } = {}) {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <CategoryPicker
        value={props.value ?? null}
        onSelect={props.onSelect ?? vi.fn()}
      />
    </QueryClientProvider>,
  );
}

function makePredefinedCategory(
  overrides: Partial<CategoryItem> = {},
): CategoryItem {
  return {
    slug: "groceries-food",
    displayName: "Groceries & Food",
    isCustom: false,
    subcategories: [
      { slug: "supermarket-grocery", displayName: "Supermarket / Grocery" },
      { slug: "produce", displayName: "Produce" },
    ],
    ...overrides,
  };
}

function makeCustomCategory(
  overrides: Partial<CategoryItem> = {},
): CategoryItem {
  return {
    slug: "my-custom-cat",
    displayName: "My Custom Category",
    isCustom: true,
    parentCategory: "other",
    subcategories: [],
    ...overrides,
  };
}

const predefinedCategories: CategoryItem[] = [
  makePredefinedCategory(),
  makePredefinedCategory({
    slug: "dining",
    displayName: "Dining",
    subcategories: [
      { slug: "fast-food-quick-service", displayName: "Fast Food / Quick Service" },
      { slug: "restaurant-dine-in", displayName: "Restaurant / Dine-In" },
    ],
  }),
  makePredefinedCategory({
    slug: "retail-shopping",
    displayName: "Retail & Shopping",
    subcategories: [],
  }),
];

describe("CategoryPicker", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchCategories.mockResolvedValue({
      categories: [...predefinedCategories],
    });
  });

  // ---- Rendering ----

  it("renders without crashing", async () => {
    renderPicker();

    await waitFor(() => {
      expect(mockFetchCategories).toHaveBeenCalled();
    });
  });

  it("shows selected category display name when value is set", async () => {
    renderPicker({ value: "groceries-food" });

    await waitFor(() => {
      expect(screen.getByText("Groceries & Food")).toBeInTheDocument();
    });
  });

  // ---- Opening the picker ----

  it("shows predefined categories when opened", async () => {
    const user = userEvent.setup();
    renderPicker();

    await waitFor(() => {
      expect(mockFetchCategories).toHaveBeenCalled();
    });

    // Click to open the picker dropdown
    const trigger = screen.getByRole("button");
    await user.click(trigger);

    await waitFor(() => {
      expect(screen.getByText("Groceries & Food")).toBeInTheDocument();
      expect(screen.getByText("Dining")).toBeInTheDocument();
      expect(screen.getByText("Retail & Shopping")).toBeInTheDocument();
    });
  });

  it("shows custom categories alongside predefined ones", async () => {
    const user = userEvent.setup();
    mockFetchCategories.mockResolvedValue({
      categories: [
        ...predefinedCategories,
        makeCustomCategory(),
      ],
    });
    renderPicker();

    await waitFor(() => {
      expect(mockFetchCategories).toHaveBeenCalled();
    });

    const trigger = screen.getByRole("button");
    await user.click(trigger);

    await waitFor(() => {
      expect(screen.getByText("My Custom Category")).toBeInTheDocument();
    });
  });

  // ---- Selecting a category ----

  it("calls onSelect with the category slug when a category is clicked", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    renderPicker({ onSelect });

    await waitFor(() => {
      expect(mockFetchCategories).toHaveBeenCalled();
    });

    const trigger = screen.getByRole("button");
    await user.click(trigger);

    await waitFor(() => {
      expect(screen.getByText("Dining")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Dining"));

    await waitFor(() => {
      expect(onSelect).toHaveBeenCalledWith("dining");
    });
  });

  // ---- Create custom category ----

  it("shows a create/add custom category option when opened", async () => {
    const user = userEvent.setup();
    renderPicker();

    await waitFor(() => {
      expect(mockFetchCategories).toHaveBeenCalled();
    });

    const trigger = screen.getByRole("button");
    await user.click(trigger);

    await waitFor(() => {
      expect(
        screen.getByText(/create|add|new.*category|custom/i),
      ).toBeInTheDocument();
    });
  });

  it("opens a create dialog when add custom category is clicked", async () => {
    const user = userEvent.setup();
    renderPicker();

    await waitFor(() => {
      expect(mockFetchCategories).toHaveBeenCalled();
    });

    const trigger = screen.getByRole("button");
    await user.click(trigger);

    await waitFor(() => {
      expect(
        screen.getByText(/create|add|new.*category|custom/i),
      ).toBeInTheDocument();
    });

    // Click the create/add option
    const createOption = screen.getByText(/create|add|new.*category|custom/i);
    await user.click(createOption);

    // Dialog should appear with a text input for the display name
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
  });

  it("creates a custom category via the dialog", async () => {
    const user = userEvent.setup();
    mockCreateCategory.mockResolvedValue({
      slug: "work-expenses",
      displayName: "Work Expenses",
      parentCategory: null,
      isCustom: true,
    });

    renderPicker();

    await waitFor(() => {
      expect(mockFetchCategories).toHaveBeenCalled();
    });

    // Open picker
    const trigger = screen.getByRole("button");
    await user.click(trigger);

    await waitFor(() => {
      expect(
        screen.getByText(/create|add|new.*category|custom/i),
      ).toBeInTheDocument();
    });

    // Click create
    await user.click(screen.getByText(/create|add|new.*category|custom/i));

    // Wait for dialog
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    // Type a name in the dialog input
    const inputField = screen.getByRole("textbox");
    await user.type(inputField, "Work Expenses");

    // Submit/create
    const submitButton = screen.getByRole("button", {
      name: /create|save|add|submit/i,
    });
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockCreateCategory).toHaveBeenCalledWith(
        expect.objectContaining({
          displayName: "Work Expenses",
        }),
      );
    });
  });

  // ---- Delete custom category (two-step confirm) ----

  it("shows a delete button for custom categories", async () => {
    const user = userEvent.setup();
    mockFetchCategories.mockResolvedValue({
      categories: [
        ...predefinedCategories,
        makeCustomCategory(),
      ],
    });
    renderPicker();

    await waitFor(() => {
      expect(mockFetchCategories).toHaveBeenCalled();
    });

    const trigger = screen.getByRole("button");
    await user.click(trigger);

    await waitFor(() => {
      expect(screen.getByText("My Custom Category")).toBeInTheDocument();
    });

    // Custom categories should have a delete button
    expect(
      screen.getByRole("button", { name: /delete my custom category/i }),
    ).toBeInTheDocument();
  });

  it("calls delete API after two-step confirmation", async () => {
    const user = userEvent.setup();
    mockFetchCategories.mockResolvedValue({
      categories: [
        ...predefinedCategories,
        makeCustomCategory(),
      ],
    });
    mockDeleteCategory.mockResolvedValue(undefined);
    renderPicker();

    await waitFor(() => {
      expect(mockFetchCategories).toHaveBeenCalled();
    });

    const trigger = screen.getByRole("button");
    await user.click(trigger);

    await waitFor(() => {
      expect(screen.getByText("My Custom Category")).toBeInTheDocument();
    });

    // Step 1: Click initial delete button
    await user.click(
      screen.getByRole("button", { name: /delete my custom category/i }),
    );

    // Step 2: Click confirm delete button
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /confirm delete/i }),
      ).toBeInTheDocument();
    });

    await user.click(
      screen.getByRole("button", { name: /confirm delete/i }),
    );

    await waitFor(() => {
      expect(mockDeleteCategory).toHaveBeenCalledWith("my-custom-cat");
    });
  });

  it("does not show delete buttons for predefined categories", async () => {
    const user = userEvent.setup();
    mockFetchCategories.mockResolvedValue({
      categories: [
        makePredefinedCategory({
          slug: "groceries-food",
          displayName: "Groceries & Food",
        }),
      ],
    });
    renderPicker();

    await waitFor(() => {
      expect(mockFetchCategories).toHaveBeenCalled();
    });

    const trigger = screen.getByRole("button");
    await user.click(trigger);

    await waitFor(() => {
      expect(screen.getByText("Groceries & Food")).toBeInTheDocument();
    });

    // No delete buttons should be present for predefined categories
    const deleteButtons = screen.queryAllByRole("button", {
      name: /delete.*groceries/i,
    });
    expect(deleteButtons.length).toBe(0);
  });

  // ---- Loading state ----

  it("renders the trigger button even while categories are loading", () => {
    mockFetchCategories.mockReturnValue(new Promise(() => {}));
    renderPicker();

    expect(screen.getByRole("button")).toBeInTheDocument();
  });

  // ---- Updating selection ----

  it("calls onSelect when a new category is selected", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    renderPicker({ value: "groceries-food", onSelect });

    await waitFor(() => {
      expect(screen.getByText("Groceries & Food")).toBeInTheDocument();
    });

    const trigger = screen.getByRole("button");
    await user.click(trigger);

    await waitFor(() => {
      expect(screen.getByText("Dining")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Dining"));

    expect(onSelect).toHaveBeenCalledWith("dining");
  });

  // ---- Null value (no category selected) ----

  it("handles null value (no category selected) without crashing", async () => {
    renderPicker({ value: null });

    await waitFor(() => {
      expect(mockFetchCategories).toHaveBeenCalled();
    });

    // Should render a button (trigger) without crashing
    expect(screen.getByRole("button")).toBeInTheDocument();
  });
});
