import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useReceipts } from "@/hooks/useReceipts";
import type { ReceiptSort } from "@/api/receipts";
import ReceiptCard from "@/components/ReceiptCard";
import { ReceiptListSkeleton } from "@/components/LoadingSkeleton";
import { NoReceiptsEmpty } from "@/components/EmptyState";
import { cn } from "@/lib/utils";

const SORT_OPTIONS: { value: ReceiptSort; label: string }[] = [
  { value: "receiptDate", label: "Receipt Date" },
  { value: "scanDate", label: "Scan Date" },
];

export default function ReceiptsPage() {
  const [sort, setSort] = useState<ReceiptSort>("receiptDate");
  const {
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useReceipts(sort);

  if (isLoading) {
    return <ReceiptListSkeleton />;
  }

  if (error) {
    return (
      <div className="py-20 text-center">
        <p className="text-destructive text-sm">
          Failed to load receipts. Please try again.
        </p>
      </div>
    );
  }

  const receipts = data?.pages.flatMap((page) => page.receipts) ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Receipts</h1>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Sort:</span>
          <div className="inline-flex rounded-lg border p-0.5">
            {SORT_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setSort(opt.value)}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  sort === opt.value
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {receipts.length === 0 ? (
        <NoReceiptsEmpty />
      ) : (
        <div className="space-y-3">
          {receipts.map((receipt) => (
            <ReceiptCard key={receipt.receiptId} receipt={receipt} />
          ))}
        </div>
      )}

      {hasNextPage && (
        <div className="flex justify-center pt-2">
          <Button
            variant="outline"
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage && (
              <Loader2 className="size-4 animate-spin" />
            )}
            Load More
          </Button>
        </div>
      )}
    </div>
  );
}
