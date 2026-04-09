import { useCallback, useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import type { TransactionStatus } from "@/api/transactions";

const STATUS_OPTIONS: { value: TransactionStatus | ""; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "confirmed", label: "Confirmed" },
  { value: "processing", label: "Processing" },
  { value: "failed", label: "Failed" },
];

const CATEGORY_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All categories" },
  { value: "groceries-food", label: "Groceries & Food" },
  { value: "dining-restaurants", label: "Dining & Restaurants" },
  { value: "transportation", label: "Transportation" },
  { value: "shopping-retail", label: "Shopping & Retail" },
  { value: "entertainment-leisure", label: "Entertainment & Leisure" },
  { value: "health-wellness", label: "Health & Wellness" },
  { value: "home-garden", label: "Home & Garden" },
  { value: "utilities-bills", label: "Utilities & Bills" },
  { value: "travel-lodging", label: "Travel & Lodging" },
  { value: "education-office", label: "Education & Office" },
  { value: "personal-care", label: "Personal Care" },
  { value: "gifts-donations", label: "Gifts & Donations" },
  { value: "other", label: "Other" },
];

export interface FilterValues {
  startDate: string;
  endDate: string;
  category: string;
  status: TransactionStatus | "";
  merchant: string;
}

interface TransactionFiltersProps {
  values: FilterValues;
  onChange: (values: FilterValues) => void;
}

const DEBOUNCE_MS = 300;

export default function TransactionFilters({
  values,
  onChange,
}: TransactionFiltersProps) {
  const [merchantInput, setMerchantInput] = useState(values.merchant);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setMerchantInput(values.merchant);
  }, [values.merchant]);

  const handleMerchantChange = useCallback(
    (value: string) => {
      setMerchantInput(value);
      if (debounceRef.current !== null) {
        clearTimeout(debounceRef.current);
      }
      debounceRef.current = setTimeout(() => {
        onChange({ ...values, merchant: value });
      }, DEBOUNCE_MS);
    },
    [onChange, values],
  );

  useEffect(() => {
    return () => {
      if (debounceRef.current !== null) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  const handleChange = useCallback(
    (field: keyof FilterValues, value: string) => {
      onChange({ ...values, [field]: value });
    },
    [onChange, values],
  );

  return (
    <fieldset className="space-y-3">
      <legend className="sr-only">Transaction filters</legend>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div>
          <label
            htmlFor="filter-start-date"
            className="text-muted-foreground mb-1 block text-xs font-medium"
          >
            Start date
          </label>
          <Input
            id="filter-start-date"
            type="date"
            value={values.startDate}
            onChange={(e) => handleChange("startDate", e.target.value)}
          />
        </div>

        <div>
          <label
            htmlFor="filter-end-date"
            className="text-muted-foreground mb-1 block text-xs font-medium"
          >
            End date
          </label>
          <Input
            id="filter-end-date"
            type="date"
            value={values.endDate}
            onChange={(e) => handleChange("endDate", e.target.value)}
          />
        </div>

        <div>
          <label
            htmlFor="filter-category"
            className="text-muted-foreground mb-1 block text-xs font-medium"
          >
            Category
          </label>
          <select
            id="filter-category"
            value={values.category}
            onChange={(e) => handleChange("category", e.target.value)}
            className="border-input bg-background flex h-9 w-full rounded-md border px-3 py-1 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]"
          >
            {CATEGORY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="filter-status"
            className="text-muted-foreground mb-1 block text-xs font-medium"
          >
            Status
          </label>
          <select
            id="filter-status"
            value={values.status}
            onChange={(e) => handleChange("status", e.target.value)}
            className="border-input bg-background flex h-9 w-full rounded-md border px-3 py-1 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="filter-merchant"
            className="text-muted-foreground mb-1 block text-xs font-medium"
          >
            Merchant
          </label>
          <Input
            id="filter-merchant"
            type="search"
            placeholder="Search merchant..."
            value={merchantInput}
            onChange={(e) => handleMerchantChange(e.target.value)}
          />
        </div>
      </div>
    </fieldset>
  );
}
