import { useInfiniteQuery } from "@tanstack/react-query";
import { getValidIdToken } from "@/lib/auth";

const API_URL = import.meta.env.VITE_API_URL ?? "";

interface ReceiptListItem {
  receiptId: string;
  receiptDate: string | null;
  merchant: string | null;
  total: number | null;
  category: string | null;
  subcategory: string | null;
  categoryDisplay: string | null;
  subcategoryDisplay: string | null;
  status: "processing" | "confirmed" | "failed";
  imageUrl: string | null;
  createdAt: string;
}

interface ReceiptListResponse {
  receipts: ReceiptListItem[];
  nextCursor: string | null;
}

export type { ReceiptListItem };

async function fetchReceipts(cursor?: string): Promise<ReceiptListResponse> {
  const token = await getValidIdToken();
  if (!token) throw new Error("Not authenticated");

  const params = new URLSearchParams();
  if (cursor) params.set("cursor", cursor);

  const url = `${API_URL}/api/receipts${params.size > 0 ? `?${params}` : ""}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch receipts (${res.status})`);
  }

  return (await res.json()) as ReceiptListResponse;
}

export function useReceipts() {
  return useInfiniteQuery({
    queryKey: ["receipts"],
    queryFn: ({ pageParam }) => fetchReceipts(pageParam as string | undefined),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
  });
}
