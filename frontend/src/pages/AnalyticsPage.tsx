import { BarChart3 } from "lucide-react";

export default function AnalyticsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
      <div className="flex flex-col items-center gap-4 py-16">
        <div className="bg-muted flex size-16 items-center justify-center rounded-full">
          <BarChart3 className="text-muted-foreground size-8" aria-hidden="true" />
        </div>
        <p className="text-muted-foreground text-lg font-medium">
          Coming Soon
        </p>
        <p className="text-muted-foreground max-w-sm text-center text-sm">
          Detailed spending analytics and charts will be available in a future update.
        </p>
      </div>
    </div>
  );
}
