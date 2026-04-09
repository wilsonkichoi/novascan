import { Link } from "react-router-dom";
import { Receipt } from "lucide-react";
import type { DashboardRecentItem } from "@/api/dashboard";

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(amount);
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr + "T00:00:00");
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

interface RecentActivityProps {
  items: DashboardRecentItem[];
}

export default function RecentActivity({ items }: RecentActivityProps) {
  if (items.length === 0) {
    return (
      <section className="bg-card rounded-lg border p-4">
        <h2 className="text-sm font-semibold">Recent Activity</h2>
        <p className="text-muted-foreground mt-3 text-sm">
          No recent receipts.
        </p>
      </section>
    );
  }

  return (
    <section className="bg-card rounded-lg border p-4">
      <h2 className="text-sm font-semibold">Recent Activity</h2>
      <ul className="mt-3 divide-y" aria-label="Recent receipts">
        {items.map((item) => (
          <li key={item.receiptId}>
            <Link
              to={`/receipts/${item.receiptId}`}
              className="hover:bg-accent/50 flex items-center gap-3 rounded-md px-1 py-2.5 transition-colors"
            >
              <div className="bg-muted flex size-8 shrink-0 items-center justify-center rounded-lg">
                <Receipt className="text-muted-foreground size-4" aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">
                  {item.merchant}
                </p>
                <p className="text-muted-foreground text-xs">
                  {formatDate(item.receiptDate)}
                  {item.categoryDisplay && (
                    <> &middot; {item.categoryDisplay}</>
                  )}
                </p>
              </div>
              <span className="shrink-0 text-sm font-semibold">
                {formatCurrency(item.total)}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
