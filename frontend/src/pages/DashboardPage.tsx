import { Loader2, Receipt } from "lucide-react";
import { useDashboard } from "@/hooks/useDashboard";
import StatCard from "@/components/StatCard";
import CategoryBreakdown from "@/components/CategoryBreakdown";
import RecentActivity from "@/components/RecentActivity";

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(amount);
}

export default function DashboardPage() {
  const { data, isLoading, error } = useDashboard();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20" role="status">
        <Loader2 className="text-muted-foreground size-6 animate-spin" aria-hidden="true" />
        <span className="sr-only">Loading dashboard</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-20 text-center">
        <p className="text-destructive text-sm">
          Failed to load dashboard. Please try again.
        </p>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>

      {/* Stat cards - single column on mobile, 3-column on desktop */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="Weekly Spending"
          value={formatCurrency(data.weeklySpent)}
          changePercent={data.weeklyChangePercent}
        />
        <StatCard
          label="Monthly Spending"
          value={formatCurrency(data.totalSpent)}
          changePercent={data.monthlyChangePercent}
        />
        <StatCard
          label="Receipts"
          value={String(data.receiptCount)}
          changePercent={null}
        />
      </div>

      {/* Receipt count breakdown */}
      <div className="text-muted-foreground flex items-center gap-1 text-xs">
        <Receipt className="size-3.5" aria-hidden="true" />
        <span>
          {data.confirmedCount} confirmed, {data.processingCount} processing, {data.failedCount} failed
        </span>
      </div>

      {/* Categories and recent activity - stacked on mobile, side-by-side on desktop */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <CategoryBreakdown categories={data.topCategories} />
        <RecentActivity items={data.recentActivity} />
      </div>
    </div>
  );
}
