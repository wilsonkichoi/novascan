import { useInfiniteQuery } from "@tanstack/react-query";
import { fetchReceipts, type ReceiptSort } from "@/api/receipts";

export function useReceipts(sort?: ReceiptSort) {
  return useInfiniteQuery({
    queryKey: ["receipts", sort],
    queryFn: ({ pageParam }) =>
      fetchReceipts(pageParam as string | undefined, sort),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
  });
}
