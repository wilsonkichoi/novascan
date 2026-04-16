import { useState, useCallback } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTransactions } from "@/hooks/useTransactions";
import TransactionTable, {
  TransactionCard,
} from "@/components/TransactionTable";
import TransactionFilters, {
  type FilterValues,
} from "@/components/TransactionFilters";
import { TransactionTableSkeleton } from "@/components/LoadingSkeleton";
import { NoTransactionsEmpty } from "@/components/EmptyState";
import type { SortBy, SortOrder } from "@/api/transactions";

const INITIAL_FILTERS: FilterValues = {
  startDate: "",
  endDate: "",
  category: "",
  status: "",
  merchant: "",
};

export default function TransactionsPage() {
  const [filters, setFilters] = useState<FilterValues>(INITIAL_FILTERS);
  const [sortBy, setSortBy] = useState<SortBy>("date");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");

  const hasInvalidDateRange =
    filters.startDate !== "" &&
    filters.endDate !== "" &&
    filters.startDate > filters.endDate;

  const queryFilters = {
    ...(filters.startDate ? { startDate: filters.startDate } : {}),
    ...(filters.endDate ? { endDate: filters.endDate } : {}),
    ...(filters.category ? { category: filters.category } : {}),
    ...(filters.status ? { status: filters.status as "processing" | "confirmed" | "failed" } : {}),
    ...(filters.merchant ? { merchant: filters.merchant } : {}),
    sortBy,
    sortOrder,
  };

  const {
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useTransactions(queryFilters, { enabled: !hasInvalidDateRange });

  const handleSort = useCallback(
    (field: SortBy) => {
      if (field === sortBy) {
        setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
      } else {
        setSortBy(field);
        setSortOrder("desc");
      }
    },
    [sortBy],
  );

  const transactions = data?.pages.flatMap((page) => page.transactions) ?? [];
  const totalCount = data?.pages[0]?.totalCount ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold tracking-tight">Transactions</h1>
        {!isLoading && !error && (
          <p className="text-muted-foreground text-sm">
            {totalCount} {totalCount === 1 ? "transaction" : "transactions"}
          </p>
        )}
      </div>

      <TransactionFilters values={filters} onChange={setFilters} />

      {hasInvalidDateRange ? (
        <div className="py-20 text-center">
          <p className="text-destructive text-sm">
            Start date must be on or before end date.
          </p>
        </div>
      ) : isLoading ? (
        <TransactionTableSkeleton />
      ) : error ? (
        <div className="py-20 text-center">
          <p className="text-destructive text-sm">
            Failed to load transactions. Please try again.
          </p>
        </div>
      ) : transactions.length === 0 ? (
        <NoTransactionsEmpty />
      ) : (
        <>
          {/* Desktop table view (hidden below md) */}
          <div className="hidden md:block">
            <TransactionTable
              transactions={transactions}
              sortBy={sortBy}
              sortOrder={sortOrder}
              onSort={handleSort}
            />
          </div>

          {/* Mobile card view (visible below md) */}
          <div className="space-y-3 md:hidden">
            {transactions.map((txn) => (
              <TransactionCard key={txn.receiptId} transaction={txn} />
            ))}
          </div>
        </>
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
