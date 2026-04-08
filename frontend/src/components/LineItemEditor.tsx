import { useState, useCallback, useEffect, useRef } from "react";
import { Plus, Trash2, Save, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ReceiptDetailLineItem } from "@/api/receipts";

export interface LineItemEditorItem {
  /** Transient key for React rendering. Not sent to the API. */
  key: string;
  sortOrder: number;
  name: string;
  quantity: string;
  unitPrice: string;
  totalPrice: string;
  subcategory: string;
}

interface ValidationErrors {
  [key: string]: {
    name?: string;
    quantity?: string;
    unitPrice?: string;
    totalPrice?: string;
  };
}

function toEditorItems(items: ReceiptDetailLineItem[]): LineItemEditorItem[] {
  return items.map((item) => ({
    key: crypto.randomUUID(),
    sortOrder: item.sortOrder,
    name: item.name,
    quantity: String(item.quantity),
    unitPrice: String(item.unitPrice),
    totalPrice: String(item.totalPrice),
    subcategory: item.subcategory ?? "",
  }));
}

function createEmptyItem(sortOrder: number): LineItemEditorItem {
  return {
    key: crypto.randomUUID(),
    sortOrder,
    name: "",
    quantity: "1",
    unitPrice: "0",
    totalPrice: "0",
    subcategory: "",
  };
}

function validateItems(
  items: LineItemEditorItem[],
): { valid: boolean; errors: ValidationErrors } {
  const errors: ValidationErrors = {};
  let valid = true;

  for (const item of items) {
    const itemErrors: ValidationErrors[string] = {};

    if (!item.name.trim()) {
      itemErrors.name = "Name is required";
      valid = false;
    }

    const qty = Number(item.quantity);
    if (isNaN(qty) || qty <= 0) {
      itemErrors.quantity = "Must be greater than 0";
      valid = false;
    }

    const unitPrice = Number(item.unitPrice);
    if (isNaN(unitPrice) || unitPrice < 0) {
      itemErrors.unitPrice = "Must be 0 or greater";
      valid = false;
    }

    const totalPrice = Number(item.totalPrice);
    if (isNaN(totalPrice) || totalPrice < 0) {
      itemErrors.totalPrice = "Must be 0 or greater";
      valid = false;
    }

    if (Object.keys(itemErrors).length > 0) {
      errors[item.key] = itemErrors;
    }
  }

  return { valid, errors };
}

interface LineItemEditorProps {
  lineItems: ReceiptDetailLineItem[];
  onSave: (
    items: {
      sortOrder: number;
      name: string;
      quantity: number;
      unitPrice: number;
      totalPrice: number;
      subcategory?: string | null;
    }[],
  ) => void;
  onSaveSuccess?: () => void;
  isSaving: boolean;
  saveError: string | null;
}

export default function LineItemEditor({
  lineItems,
  onSave,
  onSaveSuccess,
  isSaving,
  saveError,
}: LineItemEditorProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [items, setItems] = useState<LineItemEditorItem[]>(() =>
    toEditorItems(lineItems),
  );
  const [errors, setErrors] = useState<ValidationErrors>({});
  const [pendingRemoveKey, setPendingRemoveKey] = useState<string | null>(null);

  // Exit editing mode when the parent signals save success
  const onSaveSuccessRef = useRef(onSaveSuccess);
  onSaveSuccessRef.current = onSaveSuccess;
  const prevIsSavingRef = useRef(isSaving);
  useEffect(() => {
    // Detect transition from saving -> not saving while in editing mode
    // If onSaveSuccess is provided and isSaving went from true to false, the save succeeded
    // (errors are handled separately via saveError prop)
    if (prevIsSavingRef.current && !isSaving && isEditing && !saveError) {
      setIsEditing(false);
      onSaveSuccessRef.current?.();
    }
    prevIsSavingRef.current = isSaving;
  }, [isSaving, isEditing, saveError]);

  const startEditing = useCallback(() => {
    setItems(toEditorItems(lineItems));
    setErrors({});
    setIsEditing(true);
  }, [lineItems]);

  const cancelEditing = useCallback(() => {
    setItems(toEditorItems(lineItems));
    setErrors({});
    setIsEditing(false);
    setPendingRemoveKey(null);
  }, [lineItems]);

  const addItem = useCallback(() => {
    setItems((prev) => {
      const nextOrder = prev.length > 0
        ? Math.max(...prev.map((i) => i.sortOrder)) + 1
        : 1;
      return [...prev, createEmptyItem(nextOrder)];
    });
  }, []);

  const updateField = useCallback(
    (key: string, field: keyof LineItemEditorItem, value: string) => {
      setItems((prev) =>
        prev.map((item) =>
          item.key === key ? { ...item, [field]: value } : item,
        ),
      );
      // Clear the specific field error when user types
      setErrors((prev) => {
        if (!prev[key]) return prev;
        const updated = { ...prev[key] };
        delete updated[field as keyof (typeof updated)];
        if (Object.keys(updated).length === 0) {
          const rest = Object.fromEntries(
            Object.entries(prev).filter(([k]) => k !== key),
          );
          return rest;
        }
        return { ...prev, [key]: updated };
      });
    },
    [],
  );

  const confirmRemove = useCallback((key: string) => {
    setPendingRemoveKey(key);
  }, []);

  const cancelRemove = useCallback(() => {
    setPendingRemoveKey(null);
  }, []);

  const executeRemove = useCallback(() => {
    if (!pendingRemoveKey) return;
    setItems((prev) => {
      const filtered = prev.filter((item) => item.key !== pendingRemoveKey);
      // Reassign sortOrder after removal
      return filtered.map((item, idx) => ({ ...item, sortOrder: idx + 1 }));
    });
    setErrors((prev) => {
      return Object.fromEntries(
        Object.entries(prev).filter(([k]) => k !== pendingRemoveKey),
      );
    });
    setPendingRemoveKey(null);
  }, [pendingRemoveKey]);

  const handleSave = useCallback(() => {
    const { valid, errors: validationErrors } = validateItems(items);
    setErrors(validationErrors);
    if (!valid) return;

    const payload = items.map((item, idx) => ({
      sortOrder: idx + 1,
      name: item.name.trim(),
      quantity: Number(item.quantity),
      unitPrice: Number(item.unitPrice),
      totalPrice: Number(item.totalPrice),
      subcategory: item.subcategory.trim() || null,
    }));

    onSave(payload);
  }, [items, onSave]);

  // Read-only view: show table of line items with Edit button
  if (!isEditing) {
    return (
      <div className="rounded-lg border">
        <div className="flex items-center justify-between p-4 pb-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Line Items
          </h2>
          <Button
            variant="outline"
            size="sm"
            onClick={startEditing}
            aria-label="Edit line items"
          >
            Edit
          </Button>
        </div>
        {lineItems.length === 0 ? (
          <p className="px-4 pb-4 text-sm text-muted-foreground">
            No line items.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead className="text-right">Unit Price</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                  <TableHead className="hidden sm:table-cell">
                    Subcategory
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {lineItems.map((item) => (
                  <TableRow key={item.sortOrder}>
                    <TableCell className="font-medium">{item.name}</TableCell>
                    <TableCell className="text-right">
                      {item.quantity}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatCurrency(item.unitPrice)}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatCurrency(item.totalPrice)}
                    </TableCell>
                    <TableCell className="text-muted-foreground hidden sm:table-cell">
                      {item.subcategoryDisplay ?? "--"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    );
  }

  // Editing view
  return (
    <div className="rounded-lg border">
      <div className="flex items-center justify-between p-4 pb-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Line Items (Editing)
        </h2>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={cancelEditing}
            disabled={isSaving}
            aria-label="Cancel editing"
          >
            <X className="size-3.5" />
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={isSaving}
            aria-label="Save line items"
          >
            {isSaving ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Save className="size-3.5" />
            )}
            Save
          </Button>
        </div>
      </div>

      {saveError && (
        <p className="px-4 text-sm text-destructive" role="alert">
          {saveError}
        </p>
      )}

      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="min-w-[160px]">Name</TableHead>
              <TableHead className="min-w-[80px]">Qty</TableHead>
              <TableHead className="min-w-[100px]">Unit Price</TableHead>
              <TableHead className="min-w-[100px]">Total Price</TableHead>
              <TableHead className="hidden min-w-[120px] sm:table-cell">
                Subcategory
              </TableHead>
              <TableHead className="w-10">
                <span className="sr-only">Actions</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => {
              const itemErrors = errors[item.key];
              const isConfirmingRemove = pendingRemoveKey === item.key;
              return (
                <TableRow key={item.key}>
                  <TableCell>
                    <Input
                      value={item.name}
                      onChange={(e) =>
                        updateField(item.key, "name", e.target.value)
                      }
                      placeholder="Item name"
                      aria-label={`Name for item ${item.sortOrder}`}
                      aria-invalid={!!itemErrors?.name}
                      className="h-8 text-sm"
                      disabled={isSaving}
                    />
                    {itemErrors?.name && (
                      <p className="mt-0.5 text-xs text-destructive">
                        {itemErrors.name}
                      </p>
                    )}
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      value={item.quantity}
                      onChange={(e) =>
                        updateField(item.key, "quantity", e.target.value)
                      }
                      min="0.01"
                      step="any"
                      aria-label={`Quantity for item ${item.sortOrder}`}
                      aria-invalid={!!itemErrors?.quantity}
                      className="h-8 text-sm"
                      disabled={isSaving}
                    />
                    {itemErrors?.quantity && (
                      <p className="mt-0.5 text-xs text-destructive">
                        {itemErrors.quantity}
                      </p>
                    )}
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      value={item.unitPrice}
                      onChange={(e) =>
                        updateField(item.key, "unitPrice", e.target.value)
                      }
                      min="0"
                      step="0.01"
                      aria-label={`Unit price for item ${item.sortOrder}`}
                      aria-invalid={!!itemErrors?.unitPrice}
                      className="h-8 text-sm"
                      disabled={isSaving}
                    />
                    {itemErrors?.unitPrice && (
                      <p className="mt-0.5 text-xs text-destructive">
                        {itemErrors.unitPrice}
                      </p>
                    )}
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      value={item.totalPrice}
                      onChange={(e) =>
                        updateField(item.key, "totalPrice", e.target.value)
                      }
                      min="0"
                      step="0.01"
                      aria-label={`Total price for item ${item.sortOrder}`}
                      aria-invalid={!!itemErrors?.totalPrice}
                      className="h-8 text-sm"
                      disabled={isSaving}
                    />
                    {itemErrors?.totalPrice && (
                      <p className="mt-0.5 text-xs text-destructive">
                        {itemErrors.totalPrice}
                      </p>
                    )}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    <Input
                      value={item.subcategory}
                      onChange={(e) =>
                        updateField(item.key, "subcategory", e.target.value)
                      }
                      placeholder="Optional"
                      aria-label={`Subcategory for item ${item.sortOrder}`}
                      className="h-8 text-sm"
                      disabled={isSaving}
                    />
                  </TableCell>
                  <TableCell>
                    {isConfirmingRemove ? (
                      <div className="flex items-center gap-1">
                        <Button
                          variant="destructive"
                          size="icon-xs"
                          onClick={executeRemove}
                          disabled={isSaving}
                          aria-label={`Confirm remove item ${item.sortOrder}`}
                        >
                          <Trash2 className="size-3" />
                        </Button>
                        <Button
                          variant="outline"
                          size="icon-xs"
                          onClick={cancelRemove}
                          disabled={isSaving}
                          aria-label="Cancel remove"
                        >
                          <X className="size-3" />
                        </Button>
                      </div>
                    ) : (
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        onClick={() => confirmRemove(item.key)}
                        disabled={isSaving}
                        aria-label={`Remove item ${item.sortOrder}`}
                      >
                        <Trash2 className="size-3" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <div className="p-4 pt-2">
        <Button
          variant="outline"
          size="sm"
          onClick={addItem}
          disabled={isSaving}
          aria-label="Add line item"
        >
          <Plus className="size-3.5" />
          Add Item
        </Button>
      </div>
    </div>
  );
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(amount);
}
