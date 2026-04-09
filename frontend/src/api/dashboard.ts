import { getValidIdToken } from "@/lib/auth";

const API_URL = import.meta.env.VITE_API_URL ?? "";

export interface DashboardCategoryItem {
  category: string;
  categoryDisplay: string;
  total: number;
  percent: number;
}

export interface DashboardRecentItem {
  receiptId: string;
  merchant: string;
  total: number;
  category: string;
  categoryDisplay: string;
  receiptDate: string;
  status: string;
}

export interface DashboardSummary {
  month: string;
  totalSpent: number;
  previousMonthTotal: number | null;
  monthlyChangePercent: number | null;
  weeklySpent: number;
  previousWeekTotal: number | null;
  weeklyChangePercent: number | null;
  receiptCount: number;
  confirmedCount: number;
  processingCount: number;
  failedCount: number;
  topCategories: DashboardCategoryItem[];
  recentActivity: DashboardRecentItem[];
}

export async function fetchDashboardSummary(
  month?: string,
): Promise<DashboardSummary> {
  const token = await getValidIdToken();
  if (!token) throw new Error("Not authenticated");

  const params = new URLSearchParams();
  if (month) params.set("month", month);

  const url = `${API_URL}/api/dashboard/summary${params.size > 0 ? `?${params}` : ""}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch dashboard summary (${res.status})`);
  }

  return (await res.json()) as DashboardSummary;
}
