import { getValidIdToken } from "@/lib/auth";

const API_URL = import.meta.env.VITE_API_URL ?? "";

export type SortBy = "date" | "amount" | "merchant";
export type SortOrder = "asc" | "desc";
export type TransactionStatus = "processing" | "confirmed" | "failed";

export interface TransactionFilters {
  startDate?: string;
  endDate?: string;
  category?: string;
  merchant?: string;
  status?: TransactionStatus;
  sortBy?: SortBy;
  sortOrder?: SortOrder;
  limit?: number;
  cursor?: string;
}

export interface Transaction {
  receiptId: string;
  receiptDate: string | null;
  merchant: string | null;
  total: number | null;
  category: string | null;
  categoryDisplay: string | null;
  subcategory: string | null;
  subcategoryDisplay: string | null;
  status: TransactionStatus;
}

export interface TransactionsResponse {
  transactions: Transaction[];
  nextCursor: string | null;
  totalCount: number;
}

export async function fetchTransactions(
  filters: TransactionFilters = {},
): Promise<TransactionsResponse> {
  const token = await getValidIdToken();
  if (!token) throw new Error("Not authenticated");

  const params = new URLSearchParams();
  if (filters.startDate) params.set("startDate", filters.startDate);
  if (filters.endDate) params.set("endDate", filters.endDate);
  if (filters.category) params.set("category", filters.category);
  if (filters.merchant) params.set("merchant", filters.merchant);
  if (filters.status) params.set("status", filters.status);
  if (filters.sortBy) params.set("sortBy", filters.sortBy);
  if (filters.sortOrder) params.set("sortOrder", filters.sortOrder);
  if (filters.limit) params.set("limit", String(filters.limit));
  if (filters.cursor) params.set("cursor", filters.cursor);

  const url = `${API_URL}/api/transactions${params.size > 0 ? `?${params}` : ""}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch transactions (${res.status})`);
  }

  return (await res.json()) as TransactionsResponse;
}
