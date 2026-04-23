import { useState, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  Loader2,
  ArrowLeft,
  Trash2,
  RotateCw,
  Clock,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { useReceipt, useDeleteReceipt, useUpdateItems, useUpdateReceipt, useReprocessReceipt } from "@/hooks/useReceipt";
import { useCategories, usePipelineResults } from "@/hooks/useCategories";
import { NotFoundError } from "@/api/receipts";
import type { PipelineExtractedData, PipelineLineItem } from "@/api/categories";
import LineItemEditor from "@/components/LineItemEditor";
import CategoryPicker from "@/components/CategoryPicker";
import PipelineComparison from "@/components/PipelineComparison";

const statusConfig = {
  processing: {
    label: "Processing",
    icon: Clock,
    variant: "outline" as const,
    className: "border-yellow-300 bg-yellow-100 text-yellow-800",
  },
  confirmed: {
    label: "Confirmed",
    icon: CheckCircle2,
    variant: "outline" as const,
    className: "border-green-300 bg-green-100 text-green-800",
  },
  failed: {
    label: "Failed",
    icon: XCircle,
    variant: "destructive" as const,
    className: "border-red-300 bg-red-100 text-red-800",
  },
} as const;

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(amount);
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr + "T00:00:00");
  return date.toLocaleDateString("en-US", {
    weekday: "short",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

export default function ReceiptDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: receipt, isLoading, error } = useReceipt(id ?? "");
  const updateReceipt = useUpdateReceipt(id ?? "");
  const deleteReceipt = useDeleteReceipt();
  const reprocessReceipt = useReprocessReceipt(id ?? "");
  const updateItems = useUpdateItems(id ?? "");
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [saveItemsError, setSaveItemsError] = useState<string | null>(null);
  const [pipelineSource, setPipelineSource] = useState<"final" | "ocr-ai" | "ai-multimodal" | "ai-vision-v2">("final");
  const { data: pipelineData } = usePipelineResults(id ?? "", pipelineSource !== "final");

  const handleSaveItems = useCallback(
    (
      items: {
        sortOrder: number;
        name: string;
        quantity: number;
        unitPrice: number;
        totalPrice: number;
        subcategory?: string | null;
      }[],
    ) => {
      setSaveItemsError(null);
      updateItems.mutate(items, {
        onError: (err: Error) => {
          setSaveItemsError(err.message || "Failed to save line items");
        },
      });
    },
    [updateItems],
  );

  const { data: categoriesData } = useCategories();
  const selectedCategoryData = categoriesData?.categories.find(
    (c) => c.slug === receipt?.category,
  );
  const subcategories = selectedCategoryData?.subcategories ?? [];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20" role="status">
        <Loader2 className="text-muted-foreground size-6 animate-spin" />
        <span className="sr-only">Loading receipt details</span>
      </div>
    );
  }

  if (error) {
    if (error instanceof NotFoundError) {
      return (
        <div className="py-20 text-center">
          <h2 className="text-lg font-semibold">Receipt not found</h2>
          <p className="text-muted-foreground mt-1 text-sm">
            The receipt you are looking for does not exist or has been deleted.
          </p>
          <Button variant="outline" asChild className="mt-4">
            <Link to="/receipts">Back to Receipts</Link>
          </Button>
        </div>
      );
    }

    return (
      <div className="py-20 text-center">
        <p className="text-destructive text-sm">
          Failed to load receipt. Please try again.
        </p>
        <Button variant="outline" asChild className="mt-4">
          <Link to="/receipts">Back to Receipts</Link>
        </Button>
      </div>
    );
  }

  if (!receipt) return null;

  const config = statusConfig[receipt.status];
  const StatusIcon = config.icon;

  function handleDelete() {
    if (!id) return;
    setDeleteError(null);
    deleteReceipt.mutate(id, {
      onSuccess: () => {
        setShowDeleteDialog(false);
        navigate("/receipts");
      },
      onError: (error: Error) => {
        setDeleteError(error.message || "Failed to delete receipt");
      },
    });
  }

  return (
    <div className="space-y-6">
      {/* Header with back button and actions */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" asChild>
            <Link to="/receipts" aria-label="Back to receipts">
              <ArrowLeft className="size-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-xl font-bold tracking-tight sm:text-2xl">
              {receipt.merchant ?? "Receipt Details"}
            </h1>
            {receipt.receiptDate && (
              <p className="text-muted-foreground text-sm">
                {formatDate(receipt.receiptDate)}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge className={cn("gap-1", config.className)}>
            <StatusIcon className="size-3" />
            {config.label}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={() => reprocessReceipt.mutate()}
            disabled={reprocessReceipt.isPending || receipt.status === "processing"}
          >
            {reprocessReceipt.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <RotateCw className="size-4" />
            )}
            Re-process
          </Button>
          <Button
            variant="outline"
            size="icon-sm"
            onClick={() => {
              setDeleteError(null);
              setShowDeleteDialog(true);
            }}
            aria-label="Delete receipt"
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
      </div>

      {/* Pipeline source toggle */}
      <PipelineSourceToggle
        value={pipelineSource}
        onChange={setPipelineSource}
        rankingWinner={receipt.rankingWinner}
      />

      {/* Main content: side-by-side on desktop, stacked on mobile */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Image section */}
        <section aria-label="Receipt image">
          {receipt.imageUrl ? (
            <img
              src={receipt.imageUrl}
              alt={`Receipt from ${receipt.merchant ?? "unknown merchant"}`}
              className="w-full rounded-lg border object-contain"
              loading="lazy"
            />
          ) : (
            <div className="bg-muted flex aspect-[3/4] items-center justify-center rounded-lg border">
              <p className="text-muted-foreground text-sm">
                No image available
              </p>
            </div>
          )}
        </section>

        {/* Extracted data section */}
        {pipelineSource === "final" ? (
          <section aria-label="Receipt details" className="space-y-6">
            {/* Summary card */}
            <div className="rounded-lg border p-4">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Summary
              </h2>
              <dl className="space-y-2">
                {receipt.merchant && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground text-sm">Merchant</dt>
                    <dd className="text-sm font-medium">{receipt.merchant}</dd>
                  </div>
                )}
                {receipt.merchantAddress && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground text-sm">Address</dt>
                    <dd className="text-right text-sm">{receipt.merchantAddress}</dd>
                  </div>
                )}
                {receipt.receiptDate && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground text-sm">Date</dt>
                    <dd className="text-sm font-medium">
                      {formatDate(receipt.receiptDate)}
                    </dd>
                  </div>
                )}
                <div className="space-y-1">
                  <dt className="text-muted-foreground text-sm">Category</dt>
                  <dd>
                    <CategoryPicker
                      value={receipt.category}
                      onSelect={(slug) => {
                        updateReceipt.mutate({ category: slug, subcategory: "" });
                      }}
                    />
                  </dd>
                </div>
                {subcategories.length > 0 && (
                  <div className="space-y-1">
                    <dt className="text-muted-foreground text-sm">Subcategory</dt>
                    <dd>
                      <select
                        value={receipt.subcategory ?? ""}
                        onChange={(e) => {
                          updateReceipt.mutate({
                            subcategory: e.target.value || "",
                          });
                        }}
                        aria-label="Select subcategory"
                        className={cn(
                          "flex w-full rounded-md border px-3 py-2 text-sm",
                          "bg-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                        )}
                      >
                        <option value="">None</option>
                        {subcategories.map((sub) => (
                          <option key={sub.slug} value={sub.slug}>
                            {sub.displayName}
                          </option>
                        ))}
                      </select>
                    </dd>
                  </div>
                )}
                {subcategories.length === 0 && receipt.subcategoryDisplay && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground text-sm">Subcategory</dt>
                    <dd className="text-sm">{receipt.subcategoryDisplay}</dd>
                  </div>
                )}
                {receipt.paymentMethod && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground text-sm">Payment</dt>
                    <dd className="text-sm">{receipt.paymentMethod}</dd>
                  </div>
                )}
              </dl>
            </div>

            {/* Totals card */}
            <div className="rounded-lg border p-4">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Totals
              </h2>
              <dl className="space-y-2">
                {receipt.subtotal != null && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground text-sm">Subtotal</dt>
                    <dd className="text-sm">{formatCurrency(receipt.subtotal)}</dd>
                  </div>
                )}
                {receipt.tax != null && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground text-sm">Tax</dt>
                    <dd className="text-sm">{formatCurrency(receipt.tax)}</dd>
                  </div>
                )}
                {receipt.tip != null && (
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground text-sm">Tip</dt>
                    <dd className="text-sm">{formatCurrency(receipt.tip)}</dd>
                  </div>
                )}
                <div className="border-t pt-2">
                  <div className="flex justify-between">
                    <dt className="text-sm font-semibold">Total</dt>
                    <dd className="text-sm font-semibold">
                      {receipt.total != null
                        ? formatCurrency(receipt.total)
                        : "--"}
                    </dd>
                  </div>
                </div>
              </dl>
            </div>

          </section>
        ) : (
          <PipelineExtractedView
            pipelineType={pipelineSource}
            data={pipelineData?.results[pipelineSource]?.extractedData ?? null}
          />
        )}
      </div>

      {/* Line items — full width */}
      {pipelineSource === "final" ? (
        <LineItemEditor
          lineItems={receipt.lineItems}
          onSave={handleSaveItems}
          isSaving={updateItems.isPending}
          saveError={saveItemsError}
        />
      ) : (
        <PipelineLineItemsView
          items={pipelineData?.results[pipelineSource]?.extractedData?.lineItems ?? []}
        />
      )}

      {/* Pipeline comparison — full width */}
      <PipelineComparison receiptId={receipt.receiptId} />

      {/* Delete confirmation dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete receipt</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this receipt? This action cannot be
              undone. The receipt image and all associated data will be
              permanently removed.
            </DialogDescription>
          </DialogHeader>
          {deleteError && (
            <p className="text-destructive text-sm">{deleteError}</p>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDeleteDialog(false)}
              disabled={deleteReceipt.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteReceipt.isPending}
            >
              {deleteReceipt.isPending && (
                <Loader2 className="size-4 animate-spin" />
              )}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// --- Pipeline source toggle ---

const PIPELINE_LABELS: Record<string, string> = {
  final: "Final",
  "ocr-ai": "OCR + AI",
  "ai-multimodal": "AI Vision",
  "ai-vision-v2": "AI Vision v2",
};

type PipelineSource = "final" | "ocr-ai" | "ai-multimodal" | "ai-vision-v2";
type PipelineType = "ocr-ai" | "ai-multimodal" | "ai-vision-v2";

function PipelineSourceToggle({
  value,
  onChange,
  rankingWinner,
}: {
  value: PipelineSource;
  onChange: (v: PipelineSource) => void;
  rankingWinner: PipelineType | null;
}) {
  const options: readonly PipelineSource[] = ["final", "ocr-ai", "ai-multimodal", "ai-vision-v2"];
  return (
    <div className="flex items-center gap-2">
      <span className="text-sm font-medium text-muted-foreground">Source:</span>
      <div className="inline-flex rounded-lg border p-0.5">
        {options.map((opt) => (
          <button
            key={opt}
            type="button"
            onClick={() => onChange(opt)}
            className={cn(
              "relative rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              value === opt
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {PIPELINE_LABELS[opt]}
            {rankingWinner === opt && (
              <span className="ml-1 text-xs" title="Ranking winner">&#9733;</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

// --- Read-only pipeline extracted data view ---

function PipelineExtractedView({
  pipelineType,
  data,
}: {
  pipelineType: PipelineType;
  data: PipelineExtractedData | null;
}) {
  if (!data) {
    return (
      <section aria-label="Pipeline details" className="space-y-6">
        <div className="rounded-lg border border-dashed p-4">
          <p className="text-sm text-muted-foreground">
            No extraction data available for {PIPELINE_LABELS[pipelineType]}.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section aria-label="Pipeline details" className="space-y-6">
      <div className="rounded-lg border p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Summary
          <Badge variant="outline" className="ml-2 text-xs font-normal normal-case">
            {PIPELINE_LABELS[pipelineType]}
          </Badge>
        </h2>
        <dl className="space-y-2">
          {data.merchant?.name && (
            <div className="flex justify-between">
              <dt className="text-muted-foreground text-sm">Merchant</dt>
              <dd className="text-sm font-medium">{data.merchant.name}</dd>
            </div>
          )}
          {data.merchant?.address && (
            <div className="flex justify-between">
              <dt className="text-muted-foreground text-sm">Address</dt>
              <dd className="text-right text-sm whitespace-pre-line">{data.merchant.address}</dd>
            </div>
          )}
          {data.merchant?.phone && (
            <div className="flex justify-between">
              <dt className="text-muted-foreground text-sm">Phone</dt>
              <dd className="text-sm">{data.merchant.phone}</dd>
            </div>
          )}
          {data.receiptDate && (
            <div className="flex justify-between">
              <dt className="text-muted-foreground text-sm">Date</dt>
              <dd className="text-sm font-medium">{formatDate(data.receiptDate)}</dd>
            </div>
          )}
          {data.category && (
            <div className="flex justify-between">
              <dt className="text-muted-foreground text-sm">Category</dt>
              <dd className="text-sm">{data.category}</dd>
            </div>
          )}
          {data.subcategory && (
            <div className="flex justify-between">
              <dt className="text-muted-foreground text-sm">Subcategory</dt>
              <dd className="text-sm">{data.subcategory}</dd>
            </div>
          )}
          {data.paymentMethod && (
            <div className="flex justify-between">
              <dt className="text-muted-foreground text-sm">Payment</dt>
              <dd className="text-sm">{data.paymentMethod}</dd>
            </div>
          )}
          {data.confidence != null && (
            <div className="flex justify-between">
              <dt className="text-muted-foreground text-sm">Confidence</dt>
              <dd className="text-sm font-medium">{(data.confidence * 100).toFixed(1)}%</dd>
            </div>
          )}
        </dl>
      </div>

      <div className="rounded-lg border p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Totals
        </h2>
        <dl className="space-y-2">
          {data.subtotal != null && (
            <div className="flex justify-between">
              <dt className="text-muted-foreground text-sm">Subtotal</dt>
              <dd className="text-sm">{formatCurrency(data.subtotal)}</dd>
            </div>
          )}
          {data.tax != null && (
            <div className="flex justify-between">
              <dt className="text-muted-foreground text-sm">Tax</dt>
              <dd className="text-sm">{formatCurrency(data.tax)}</dd>
            </div>
          )}
          {data.tip != null && (
            <div className="flex justify-between">
              <dt className="text-muted-foreground text-sm">Tip</dt>
              <dd className="text-sm">{formatCurrency(data.tip)}</dd>
            </div>
          )}
          <div className="border-t pt-2">
            <div className="flex justify-between">
              <dt className="text-sm font-semibold">Total</dt>
              <dd className="text-sm font-semibold">
                {data.total != null ? formatCurrency(data.total) : "--"}
              </dd>
            </div>
          </div>
        </dl>
      </div>
    </section>
  );
}

// --- Read-only pipeline line items ---

function PipelineLineItemsView({ items }: { items: PipelineLineItem[] }) {
  const itemsTotal = items.reduce((sum, item) => sum + item.totalPrice, 0);

  return (
    <div className="rounded-lg border">
      <div className="p-4 pb-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Line Items
          <Badge variant="outline" className="ml-2 text-xs font-normal normal-case">
            Read-only
          </Badge>
        </h2>
      </div>
      {items.length === 0 ? (
        <p className="px-4 pb-4 text-sm text-muted-foreground">
          No line items extracted.
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
                <TableHead className="hidden sm:table-cell">Subcategory</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item, i) => (
                <TableRow key={i}>
                  <TableCell className="font-medium">{item.name}</TableCell>
                  <TableCell className="text-right">{item.quantity}</TableCell>
                  <TableCell className="text-right">{formatCurrency(item.unitPrice)}</TableCell>
                  <TableCell className="text-right">{formatCurrency(item.totalPrice)}</TableCell>
                  <TableCell className="text-muted-foreground hidden sm:table-cell">
                    {item.subcategory ?? "--"}
                  </TableCell>
                </TableRow>
              ))}
              <TableRow className="border-t-2">
                <TableCell colSpan={3} className="text-right text-sm font-semibold">
                  Items Total
                </TableCell>
                <TableCell className="text-right text-sm font-semibold">
                  {formatCurrency(itemsTotal)}
                </TableCell>
                <TableCell className="hidden sm:table-cell" />
              </TableRow>
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
