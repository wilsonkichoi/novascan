import { Link } from "react-router-dom";
import { Receipt, Clock, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ReceiptListItem } from "@/hooks/useReceipts";

const statusConfig = {
  processing: {
    label: "Processing",
    icon: Clock,
    bg: "bg-yellow-100 dark:bg-yellow-900/30",
    text: "text-yellow-800 dark:text-yellow-300",
  },
  confirmed: {
    label: "Confirmed",
    icon: CheckCircle2,
    bg: "bg-green-100 dark:bg-green-900/30",
    text: "text-green-800 dark:text-green-300",
  },
  failed: {
    label: "Failed",
    icon: XCircle,
    bg: "bg-red-100 dark:bg-red-900/30",
    text: "text-red-800 dark:text-red-300",
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
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function ReceiptCard({ receipt }: { receipt: ReceiptListItem }) {
  const config = statusConfig[receipt.status];
  const StatusIcon = config.icon;
  const isProcessing = receipt.status === "processing";

  return (
    <Link
      to={`/receipts/${receipt.receiptId}`}
      className="bg-card hover:bg-accent/50 flex items-center gap-4 rounded-lg border p-4 transition-colors"
    >
      <div className="bg-muted flex size-10 shrink-0 items-center justify-center rounded-lg">
        <Receipt className="text-muted-foreground size-5" />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span
            className={cn(
              "truncate text-sm font-medium",
              isProcessing && "text-muted-foreground italic",
            )}
          >
            {isProcessing ? "Processing..." : (receipt.merchant ?? "Unknown")}
          </span>
          <span
            className={cn(
              "shrink-0 text-sm font-semibold",
              isProcessing && "text-muted-foreground",
            )}
          >
            {isProcessing || receipt.total == null
              ? "--"
              : formatCurrency(receipt.total)}
          </span>
        </div>

        <div className="mt-1 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            {receipt.receiptDate && (
              <span className="text-muted-foreground text-xs">
                {formatDate(receipt.receiptDate)}
              </span>
            )}
            {receipt.categoryDisplay && (
              <>
                <span className="text-muted-foreground text-xs">&middot;</span>
                <span className="text-muted-foreground truncate text-xs">
                  {receipt.categoryDisplay}
                </span>
              </>
            )}
          </div>

          <span
            className={cn(
              "inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
              config.bg,
              config.text,
            )}
          >
            <StatusIcon className="size-3" />
            {config.label}
          </span>
        </div>
      </div>
    </Link>
  );
}
