import { useQuery } from "@tanstack/react-query";
import { fetchDashboardSummary } from "@/api/dashboard";

export function useDashboard(month?: string) {
  return useQuery({
    queryKey: ["dashboard", month],
    queryFn: () => fetchDashboardSummary(month),
  });
}
