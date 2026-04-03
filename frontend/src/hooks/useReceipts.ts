import { useInfiniteQuery } from "@tanstack/react-query";
import { fetchReceipts } from "@/api/receipts";

export function useReceipts() {
  return useInfiniteQuery({
    queryKey: ["receipts"],
    queryFn: ({ pageParam }) => fetchReceipts(pageParam as string | undefined),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
  });
}
