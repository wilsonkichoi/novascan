/** Receipt processing status */
export type ReceiptStatus =
  | "uploading"
  | "processing"
  | "confirmed"
  | "failed";

/** A single line item on a receipt */
export interface LineItem {
  description: string;
  quantity: number;
  unitPrice: number;
  totalPrice: number;
  category?: string;
}

/** A receipt record */
export interface Receipt {
  id: string;
  userId: string;
  merchantName: string;
  transactionDate: string;
  subtotal: number;
  tax: number;
  total: number;
  currency: string;
  lineItems: LineItem[];
  status: ReceiptStatus;
  imageUrl?: string;
  createdAt: string;
  updatedAt: string;
}

/** Authenticated user */
export interface User {
  id: string;
  email: string;
  groups: string[];
}

/** Dashboard spending summary */
export interface SpendingSummary {
  periodStart: string;
  periodEnd: string;
  totalSpent: number;
  transactionCount: number;
  categoryBreakdown: Record<string, number>;
}
