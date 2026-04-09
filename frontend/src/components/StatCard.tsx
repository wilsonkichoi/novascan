import { TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string;
  changePercent: number | null;
}

export default function StatCard({ label, value, changePercent }: StatCardProps) {
  const isPositive = changePercent !== null && changePercent > 0;
  const isNegative = changePercent !== null && changePercent < 0;

  return (
    <article className="bg-card rounded-lg border p-4">
      <p className="text-muted-foreground text-sm">{label}</p>
      <p className="mt-1 text-2xl font-bold tracking-tight">{value}</p>
      {changePercent !== null && (
        <div
          className={cn(
            "mt-2 inline-flex items-center gap-1 text-xs font-medium",
            isPositive && "text-red-600",
            isNegative && "text-green-600",
          )}
          aria-label={`${Math.abs(changePercent).toFixed(1)}% ${isPositive ? "increase" : "decrease"} from previous period`}
        >
          {isPositive && <TrendingUp className="size-3.5" aria-hidden="true" />}
          {isNegative && <TrendingDown className="size-3.5" aria-hidden="true" />}
          <span>{Math.abs(changePercent).toFixed(1)}%</span>
          <span className="text-muted-foreground">
            vs previous
          </span>
        </div>
      )}
    </article>
  );
}
