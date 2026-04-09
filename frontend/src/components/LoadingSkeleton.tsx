import { Skeleton } from "@/components/ui/skeleton";

export function DashboardSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading dashboard">
      <Skeleton className="h-8 w-36" />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {Array.from({ length: 3 }, (_, i) => (
          <div key={i} className="rounded-lg border p-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="mt-2 h-8 w-20" />
            <Skeleton className="mt-2 h-3 w-32" />
          </div>
        ))}
      </div>

      <Skeleton className="h-3 w-48" />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-lg border p-4">
          <Skeleton className="h-5 w-32" />
          <div className="mt-4 space-y-3">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-4 w-full" />
            ))}
          </div>
        </div>
        <div className="rounded-lg border p-4">
          <Skeleton className="h-5 w-32" />
          <div className="mt-4 space-y-3">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-4 w-full" />
            ))}
          </div>
        </div>
      </div>

      <span className="sr-only">Loading dashboard</span>
    </div>
  );
}

export function ReceiptListSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading receipts">
      <Skeleton className="h-8 w-28" />

      <div className="space-y-3">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="flex items-center gap-4 rounded-lg border p-4">
            <Skeleton className="size-10 shrink-0 rounded-lg" />
            <div className="min-w-0 flex-1 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-16" />
              </div>
              <div className="flex items-center justify-between gap-2">
                <Skeleton className="h-3 w-40" />
                <Skeleton className="h-5 w-20 rounded-full" />
              </div>
            </div>
          </div>
        ))}
      </div>

      <span className="sr-only">Loading receipts</span>
    </div>
  );
}

export function TransactionTableSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading transactions">
      <div className="flex items-center justify-between gap-4">
        <Skeleton className="h-8 w-36" />
      </div>

      {/* Desktop table skeleton */}
      <div className="hidden md:block">
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full">
            <thead className="bg-muted/50 border-b">
              <tr>
                <th className="px-4 py-3"><Skeleton className="h-3 w-12" /></th>
                <th className="px-4 py-3"><Skeleton className="h-3 w-20" /></th>
                <th className="px-4 py-3"><Skeleton className="h-3 w-20" /></th>
                <th className="px-4 py-3"><Skeleton className="h-3 w-16" /></th>
                <th className="px-4 py-3"><Skeleton className="h-3 w-14" /></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {Array.from({ length: 6 }, (_, i) => (
                <tr key={i}>
                  <td className="px-4 py-3"><Skeleton className="h-4 w-24" /></td>
                  <td className="px-4 py-3"><Skeleton className="h-4 w-28" /></td>
                  <td className="px-4 py-3"><Skeleton className="h-4 w-20" /></td>
                  <td className="px-4 py-3"><Skeleton className="ml-auto h-4 w-16" /></td>
                  <td className="px-4 py-3"><Skeleton className="h-5 w-20 rounded-full" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Mobile card skeleton */}
      <div className="space-y-3 md:hidden">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="rounded-lg border p-4">
            <div className="flex items-center justify-between gap-2">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-4 w-16" />
            </div>
            <div className="mt-2 flex items-center justify-between gap-2">
              <Skeleton className="h-3 w-36" />
              <Skeleton className="h-5 w-20 rounded-full" />
            </div>
          </div>
        ))}
      </div>

      <span className="sr-only">Loading transactions</span>
    </div>
  );
}
