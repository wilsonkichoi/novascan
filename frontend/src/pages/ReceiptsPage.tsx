import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useReceipts } from "@/hooks/useReceipts";
import ReceiptCard from "@/components/ReceiptCard";
import { ReceiptListSkeleton } from "@/components/LoadingSkeleton";
import { NoReceiptsEmpty } from "@/components/EmptyState";

export default function ReceiptsPage() {
  const {
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useReceipts();

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
      <h1 className="text-2xl font-bold tracking-tight">Receipts</h1>

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
