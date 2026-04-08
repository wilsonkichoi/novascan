import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  Loader2,
  ArrowLeft,
  Trash2,
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
import { useReceipt, useDeleteReceipt } from "@/hooks/useReceipt";
import { NotFoundError } from "@/api/receipts";

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
  const deleteReceipt = useDeleteReceipt();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

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
              {receipt.categoryDisplay && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground text-sm">Category</dt>
                  <dd className="text-sm">{receipt.categoryDisplay}</dd>
                </div>
              )}
              {receipt.subcategoryDisplay && (
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

          {/* Line items */}
          {receipt.lineItems.length > 0 && (
            <div className="rounded-lg border">
              <h2 className="p-4 pb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Line Items
              </h2>
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
                    {receipt.lineItems.map((item) => (
                      <TableRow key={item.sortOrder}>
                        <TableCell className="font-medium">
                          {item.name}
                        </TableCell>
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
            </div>
          )}
        </section>
      </div>

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
