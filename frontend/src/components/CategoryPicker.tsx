import { useState } from "react";
import { ChevronDown, Plus, Trash2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import {
  useCategories,
  useCreateCategory,
  useDeleteCategory,
} from "@/hooks/useCategories";
import type { CategoryItem } from "@/api/categories";

interface CategoryPickerProps {
  value: string | null;
  onSelect: (slug: string) => void;
}

export default function CategoryPicker({ value, onSelect }: CategoryPickerProps) {
  const { data, isLoading } = useCategories();
  const createCategory = useCreateCategory();
  const deleteCategoryMutation = useDeleteCategory();
  const [isOpen, setIsOpen] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newDisplayName, setNewDisplayName] = useState("");
  const [newParentCategory, setNewParentCategory] = useState<string | "">("");
  const [createError, setCreateError] = useState<string | null>(null);

  const categories = data?.categories ?? [];
  const predefined = categories.filter((c) => !c.isCustom);
  const custom = categories.filter((c) => c.isCustom);

  // Find the display name for the currently selected category
  const selectedCategory = categories.find((c) => c.slug === value);
  const displayLabel = selectedCategory?.displayName ?? value ?? "Select category";

  function handleSelect(slug: string) {
    onSelect(slug);
    setIsOpen(false);
  }

  function handleDelete(
    e: React.MouseEvent,
    slug: string,
  ) {
    e.stopPropagation();
    deleteCategoryMutation.mutate(slug);
  }

  function handleOpenCreate() {
    setIsOpen(false);
    setNewDisplayName("");
    setNewParentCategory("");
    setCreateError(null);
    setShowCreateModal(true);
  }

  function handleCreateSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmedName = newDisplayName.trim();
    if (!trimmedName) {
      setCreateError("Display name is required");
      return;
    }
    if (trimmedName.length > 100) {
      setCreateError("Display name must be 100 characters or less");
      return;
    }
    setCreateError(null);
    createCategory.mutate(
      {
        displayName: trimmedName,
        parentCategory: newParentCategory || null,
      },
      {
        onSuccess: (result) => {
          setShowCreateModal(false);
          onSelect(result.slug);
        },
        onError: (error: Error) => {
          setCreateError(error.message);
        },
      },
    );
  }

  return (
    <>
      <div className="relative">
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          disabled={isLoading}
          aria-haspopup="listbox"
          aria-expanded={isOpen}
          aria-label="Select category"
          className={cn(
            "flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm",
            "bg-background hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
            isLoading && "opacity-50",
          )}
        >
          <span className={cn(!selectedCategory && !value && "text-muted-foreground")}>
            {isLoading ? "Loading..." : displayLabel}
          </span>
          <ChevronDown className="text-muted-foreground size-4 shrink-0" />
        </button>

        {isOpen && (
          <>
            {/* Backdrop to close dropdown */}
            <div
              className="fixed inset-0 z-40"
              onClick={() => setIsOpen(false)}
              aria-hidden="true"
            />
            <ul
              role="listbox"
              aria-label="Category options"
              className={cn(
                "absolute z-50 mt-1 max-h-72 w-full overflow-y-auto rounded-md border bg-background shadow-lg",
              )}
            >
              {/* Predefined categories */}
              {predefined.length > 0 && (
                <li
                  role="presentation"
                  className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                >
                  Categories
                </li>
              )}
              {predefined.map((cat) => (
                <CategoryOption
                  key={cat.slug}
                  category={cat}
                  isSelected={cat.slug === value}
                  onSelect={handleSelect}
                />
              ))}

              {/* Custom categories */}
              {custom.length > 0 && (
                <li
                  role="presentation"
                  className="mt-1 border-t px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                >
                  Custom
                </li>
              )}
              {custom.map((cat) => (
                <CategoryOption
                  key={cat.slug}
                  category={cat}
                  isSelected={cat.slug === value}
                  onSelect={handleSelect}
                  onDelete={handleDelete}
                  isDeleting={
                    deleteCategoryMutation.isPending &&
                    deleteCategoryMutation.variables === cat.slug
                  }
                />
              ))}

              {/* Create custom category option */}
              <li role="presentation" className="border-t">
                <button
                  type="button"
                  role="option"
                  aria-selected={false}
                  onClick={handleOpenCreate}
                  className="flex w-full items-center gap-2 px-3 py-2 text-sm text-primary hover:bg-accent"
                >
                  <Plus className="size-4" />
                  Create Custom Category
                </button>
              </li>
            </ul>
          </>
        )}
      </div>

      {/* Create custom category modal */}
      <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Custom Category</DialogTitle>
            <DialogDescription>
              Add a new category for organizing your receipts.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreateSubmit} className="space-y-4">
            <div className="space-y-2">
              <label
                htmlFor="category-display-name"
                className="text-sm font-medium"
              >
                Display Name
              </label>
              <Input
                id="category-display-name"
                value={newDisplayName}
                onChange={(e) => setNewDisplayName(e.target.value)}
                placeholder="e.g., Costco, Pet Insurance"
                maxLength={100}
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <label
                htmlFor="category-parent"
                className="text-sm font-medium"
              >
                Parent Category{" "}
                <span className="text-muted-foreground font-normal">
                  (optional)
                </span>
              </label>
              <select
                id="category-parent"
                value={newParentCategory}
                onChange={(e) => setNewParentCategory(e.target.value)}
                className={cn(
                  "flex w-full rounded-md border px-3 py-2 text-sm",
                  "bg-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                )}
              >
                <option value="">None</option>
                {predefined.map((cat) => (
                  <option key={cat.slug} value={cat.slug}>
                    {cat.displayName}
                  </option>
                ))}
              </select>
            </div>
            {createError && (
              <p className="text-destructive text-sm">{createError}</p>
            )}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowCreateModal(false)}
                disabled={createCategory.isPending}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createCategory.isPending}>
                {createCategory.isPending && (
                  <Loader2 className="size-4 animate-spin" />
                )}
                Create
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

// --- Category option item ---

interface CategoryOptionProps {
  category: CategoryItem;
  isSelected: boolean;
  onSelect: (slug: string) => void;
  onDelete?: (e: React.MouseEvent, slug: string) => void;
  isDeleting?: boolean;
}

function CategoryOption({
  category,
  isSelected,
  onSelect,
  onDelete,
  isDeleting,
}: CategoryOptionProps) {
  return (
    <li
      role="option"
      aria-selected={isSelected}
      className={cn(
        "flex cursor-pointer items-center justify-between px-3 py-2 text-sm hover:bg-accent",
        isSelected && "bg-accent font-medium",
      )}
      onClick={() => onSelect(category.slug)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(category.slug);
        }
      }}
      tabIndex={0}
    >
      <span>{category.displayName}</span>
      {onDelete && (
        <button
          type="button"
          onClick={(e) => onDelete(e, category.slug)}
          disabled={isDeleting}
          aria-label={`Delete ${category.displayName}`}
          className="ml-2 rounded p-0.5 text-muted-foreground hover:text-destructive focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          {isDeleting ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <Trash2 className="size-3.5" />
          )}
        </button>
      )}
    </li>
  );
}
