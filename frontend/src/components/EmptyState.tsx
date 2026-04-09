import { Link } from "react-router-dom";
import { ScanLine, Receipt, ArrowLeftRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export function NoReceiptsEmpty() {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <div className="bg-muted flex size-16 items-center justify-center rounded-full">
        <ScanLine className="text-muted-foreground size-8" aria-hidden="true" />
      </div>
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">No receipts yet</h2>
        <p className="text-muted-foreground text-sm">
          Scan your first receipt to start tracking your spending.
        </p>
      </div>
      <Button asChild>
        <Link to="/scan">Scan your first receipt</Link>
      </Button>
    </div>
  );
}

export function NoTransactionsEmpty() {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <div className="bg-muted flex size-16 items-center justify-center rounded-full">
        <ArrowLeftRight
          className="text-muted-foreground size-8"
          aria-hidden="true"
        />
      </div>
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">No transactions found</h2>
        <p className="text-muted-foreground text-sm">
          Transactions will appear here once you scan your first receipt.
        </p>
      </div>
    </div>
  );
}

export function DashboardWelcome() {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <div className="bg-muted flex size-16 items-center justify-center rounded-full">
        <Receipt className="text-muted-foreground size-8" aria-hidden="true" />
      </div>
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Welcome to NovaScan</h2>
        <p className="text-muted-foreground text-sm">
          Start tracking your spending by scanning a receipt.
        </p>
      </div>
      <Button asChild>
        <Link to="/scan">Scan your first receipt</Link>
      </Button>
    </div>
  );
}
