import { useInfiniteQuery } from "@tanstack/react-query";
import {
  fetchTransactions,
  type TransactionFilters,
} from "@/api/transactions";

export function useTransactions(filters: Omit<TransactionFilters, "cursor">) {
  return useInfiniteQuery({
    queryKey: ["transactions", filters],
    queryFn: ({ pageParam }) =>
      fetchTransactions({ ...filters, cursor: pageParam as string | undefined }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
  });
}
