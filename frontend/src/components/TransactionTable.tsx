import { Link } from "react-router-dom";
import { ArrowUp, ArrowDown, ArrowUpDown, Clock, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Transaction, SortBy, SortOrder } from "@/api/transactions";

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

interface SortableColumnProps {
  label: string;
  field: SortBy;
  currentSort: SortBy;
  currentOrder: SortOrder;
  onSort: (field: SortBy) => void;
  className?: string;
}

function SortableColumn({
  label,
  field,
  currentSort,
  currentOrder,
  onSort,
  className,
}: SortableColumnProps) {
  const isActive = currentSort === field;
  const SortIcon = isActive
    ? currentOrder === "asc"
      ? ArrowUp
      : ArrowDown
    : ArrowUpDown;

  return (
    <th className={cn("text-muted-foreground px-4 py-3 text-left text-xs font-medium", className)}>
      <button
        type="button"
        onClick={() => onSort(field)}
        className="inline-flex items-center gap-1 hover:text-foreground"
        aria-label={`Sort by ${label}`}
      >
        {label}
        <SortIcon
          className={cn(
            "size-3",
            isActive ? "text-foreground" : "text-muted-foreground/50",
          )}
        />
      </button>
    </th>
  );
}

interface TransactionTableProps {
  transactions: Transaction[];
  sortBy: SortBy;
  sortOrder: SortOrder;
  onSort: (field: SortBy) => void;
}

export default function TransactionTable({
  transactions,
  sortBy,
  sortOrder,
  onSort,
}: TransactionTableProps) {
  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full">
        <thead className="bg-muted/50 border-b">
          <tr>
            <SortableColumn
              label="Date"
              field="date"
              currentSort={sortBy}
              currentOrder={sortOrder}
              onSort={onSort}
            />
            <SortableColumn
              label="Merchant"
              field="merchant"
              currentSort={sortBy}
              currentOrder={sortOrder}
              onSort={onSort}
            />
            <th className="text-muted-foreground px-4 py-3 text-left text-xs font-medium">
              Category
            </th>
            <SortableColumn
              label="Amount"
              field="amount"
              currentSort={sortBy}
              currentOrder={sortOrder}
              onSort={onSort}
              className="text-right"
            />
            <th className="text-muted-foreground px-4 py-3 text-left text-xs font-medium">
              Status
            </th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {transactions.map((txn) => {
            const config = statusConfig[txn.status];
            const StatusIcon = config.icon;
            const isProcessing = txn.status === "processing";

            return (
              <tr
                key={txn.receiptId}
                className="hover:bg-accent/50 transition-colors"
              >
                <td className="px-4 py-3 text-sm">
                  <Link
                    to={`/receipts/${txn.receiptId}`}
                    className="hover:underline"
                  >
                    {txn.receiptDate ? formatDate(txn.receiptDate) : "--"}
                  </Link>
                </td>
                <td
                  className={cn(
                    "px-4 py-3 text-sm font-medium",
                    isProcessing && "text-muted-foreground italic",
                  )}
                >
                  {isProcessing
                    ? "Processing..."
                    : (txn.merchant ?? "Unknown")}
                </td>
                <td className="text-muted-foreground px-4 py-3 text-sm">
                  {txn.categoryDisplay ?? "--"}
                </td>
                <td
                  className={cn(
                    "px-4 py-3 text-right text-sm font-semibold",
                    isProcessing && "text-muted-foreground",
                  )}
                >
                  {isProcessing || txn.total == null
                    ? "--"
                    : formatCurrency(txn.total)}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
                      config.bg,
                      config.text,
                    )}
                  >
                    <StatusIcon className="size-3" />
                    {config.label}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Mobile card view for transactions at narrow viewports */
export function TransactionCard({
  transaction,
}: {
  transaction: Transaction;
}) {
  const config = statusConfig[transaction.status];
  const StatusIcon = config.icon;
  const isProcessing = transaction.status === "processing";

  return (
    <Link
      to={`/receipts/${transaction.receiptId}`}
      className="bg-card hover:bg-accent/50 block rounded-lg border p-4 transition-colors"
    >
      <div className="flex items-center justify-between gap-2">
        <span
          className={cn(
            "truncate text-sm font-medium",
            isProcessing && "text-muted-foreground italic",
          )}
        >
          {isProcessing
            ? "Processing..."
            : (transaction.merchant ?? "Unknown")}
        </span>
        <span
          className={cn(
            "shrink-0 text-sm font-semibold",
            isProcessing && "text-muted-foreground",
          )}
        >
          {isProcessing || transaction.total == null
            ? "--"
            : formatCurrency(transaction.total)}
        </span>
      </div>

      <div className="mt-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {transaction.receiptDate && (
            <span className="text-muted-foreground text-xs">
              {formatDate(transaction.receiptDate)}
            </span>
          )}
          {transaction.categoryDisplay && (
            <>
              <span className="text-muted-foreground text-xs">&middot;</span>
              <span className="text-muted-foreground truncate text-xs">
                {transaction.categoryDisplay}
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
    </Link>
  );
}
