import type { DashboardCategoryItem } from "@/api/dashboard";

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(amount);
}

interface CategoryBreakdownProps {
  categories: DashboardCategoryItem[];
}

export default function CategoryBreakdown({ categories }: CategoryBreakdownProps) {
  if (categories.length === 0) {
    return (
      <section className="bg-card rounded-lg border p-4">
        <h2 className="text-sm font-semibold">Top Categories</h2>
        <p className="text-muted-foreground mt-3 text-sm">
          No category data yet.
        </p>
      </section>
    );
  }

  return (
    <section className="bg-card rounded-lg border p-4">
      <h2 className="text-sm font-semibold">Top Categories</h2>
      <ul className="mt-3 space-y-3" aria-label="Top spending categories">
        {categories.map((cat) => (
          <li key={cat.category} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span>{cat.categoryDisplay}</span>
              <span className="font-medium">{formatCurrency(cat.total)}</span>
            </div>
            <div className="bg-muted h-2 overflow-hidden rounded-full">
              <div
                className="bg-primary h-full rounded-full"
                style={{ width: `${Math.min(cat.percent, 100)}%` }}
                role="progressbar"
                aria-valuenow={cat.percent}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`${cat.categoryDisplay}: ${cat.percent.toFixed(1)}%`}
              />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
