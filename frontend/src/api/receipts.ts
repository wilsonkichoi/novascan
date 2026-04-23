import { getValidIdToken } from "@/lib/auth";

const API_URL = import.meta.env.VITE_API_URL ?? "";

interface UploadUrlRequest {
  files: { fileName: string; contentType: string; fileSize: number }[];
}

interface UploadUrlReceipt {
  receiptId: string;
  uploadUrl: string;
  imageKey: string;
  expiresIn: number;
}

interface UploadUrlResponse {
  receipts: UploadUrlReceipt[];
}

interface ApiError {
  error: { code: string; message: string };
}

export type { UploadUrlReceipt };

export async function requestUploadUrls(
  files: File[],
): Promise<UploadUrlReceipt[]> {
  const token = await getValidIdToken();
  if (!token) {
    throw new Error("Not authenticated");
  }

  const body: UploadUrlRequest = {
    files: files.map((f) => ({
      fileName: f.name,
      contentType: f.type,
      fileSize: f.size,
    })),
  };

  const res = await fetch(`${API_URL}/api/receipts/upload-urls`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errorBody = (await res.json().catch(() => null)) as ApiError | null;
    const message =
      errorBody?.error?.message ?? `Upload URL request failed (${res.status})`;
    throw new Error(message);
  }

  const data = (await res.json()) as UploadUrlResponse;
  return data.receipts;
}

// --- Receipt list types and fetch ---

export interface ReceiptListItem {
  receiptId: string;
  receiptDate: string | null;
  merchant: string | null;
  total: number | null;
  category: string | null;
  subcategory: string | null;
  categoryDisplay: string | null;
  subcategoryDisplay: string | null;
  status: "processing" | "confirmed" | "failed";
  imageUrl: string | null;
  createdAt: string;
}

export interface ReceiptListResponse {
  receipts: ReceiptListItem[];
  nextCursor: string | null;
}

export type ReceiptSort = "receiptDate" | "scanDate";

export async function fetchReceipts(
  cursor?: string,
  sort?: ReceiptSort,
): Promise<ReceiptListResponse> {
  const token = await getValidIdToken();
  if (!token) throw new Error("Not authenticated");

  const params = new URLSearchParams();
  if (cursor) params.set("cursor", cursor);
  if (sort) params.set("sort", sort);

  const url = `${API_URL}/api/receipts${params.size > 0 ? `?${params}` : ""}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch receipts (${res.status})`);
  }

  return (await res.json()) as ReceiptListResponse;
}

// --- Receipt detail types and API functions ---

export interface ReceiptDetailLineItem {
  sortOrder: number;
  name: string;
  quantity: number;
  unitPrice: number;
  totalPrice: number;
  subcategory: string | null;
  subcategoryDisplay: string | null;
}

export interface ReceiptDetail {
  receiptId: string;
  receiptDate: string | null;
  merchant: string | null;
  merchantAddress: string | null;
  total: number | null;
  subtotal: number | null;
  tax: number | null;
  tip: number | null;
  category: string | null;
  categoryDisplay: string | null;
  subcategory: string | null;
  subcategoryDisplay: string | null;
  status: "processing" | "confirmed" | "failed";
  usedFallback: boolean | null;
  rankingWinner: "ocr-ai" | "ai-multimodal" | null;
  imageUrl: string | null;
  paymentMethod: string | null;
  lineItems: ReceiptDetailLineItem[];
  createdAt: string;
  updatedAt: string | null;
}

export async function getReceipt(id: string): Promise<ReceiptDetail> {
  const token = await getValidIdToken();
  if (!token) throw new Error("Not authenticated");

  const res = await fetch(`${API_URL}/api/receipts/${encodeURIComponent(id)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (res.status === 404) {
    throw new NotFoundError("Receipt not found");
  }

  if (!res.ok) {
    throw new Error(`Failed to fetch receipt (${res.status})`);
  }

  return (await res.json()) as ReceiptDetail;
}

export interface ReceiptUpdatePayload {
  merchant?: string;
  merchantAddress?: string;
  receiptDate?: string;
  category?: string;
  subcategory?: string;
  total?: number;
  subtotal?: number;
  tax?: number;
  tip?: number | null;
  paymentMethod?: string;
}

export async function updateReceipt(
  id: string,
  data: ReceiptUpdatePayload,
): Promise<ReceiptDetail> {
  const token = await getValidIdToken();
  if (!token) throw new Error("Not authenticated");

  const res = await fetch(`${API_URL}/api/receipts/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    const errorBody = (await res.json().catch(() => null)) as ApiError | null;
    const message =
      errorBody?.error?.message ?? `Failed to update receipt (${res.status})`;
    throw new Error(message);
  }

  return (await res.json()) as ReceiptDetail;
}

export async function deleteReceipt(id: string): Promise<void> {
  const token = await getValidIdToken();
  if (!token) throw new Error("Not authenticated");

  const res = await fetch(`${API_URL}/api/receipts/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (res.status === 404) {
    throw new NotFoundError("Receipt not found");
  }

  if (!res.ok) {
    throw new Error(`Failed to delete receipt (${res.status})`);
  }
}

export interface LineItemInput {
  sortOrder: number;
  name: string;
  quantity: number;
  unitPrice: number;
  totalPrice: number;
  subcategory?: string | null;
}

export async function updateItems(
  id: string,
  items: LineItemInput[],
): Promise<ReceiptDetail> {
  const token = await getValidIdToken();
  if (!token) throw new Error("Not authenticated");

  const res = await fetch(
    `${API_URL}/api/receipts/${encodeURIComponent(id)}/items`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ items }),
    },
  );

  if (!res.ok) {
    const errorBody = (await res.json().catch(() => null)) as ApiError | null;
    const message =
      errorBody?.error?.message ?? `Failed to update items (${res.status})`;
    throw new Error(message);
  }

  return (await res.json()) as ReceiptDetail;
}

/** Error thrown when a resource is not found (404). */
export class NotFoundError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NotFoundError";
  }
}

// --- S3 upload ---

export function uploadFileToS3(
  url: string,
  file: File,
  onProgress?: (pct: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.setRequestHeader("Content-Type", file.type);

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(new Error(`S3 upload failed (${xhr.status})`));
      }
    });

    xhr.addEventListener("error", () => {
      reject(new Error("Network error during upload"));
    });

    xhr.addEventListener("abort", () => {
      reject(new Error("Upload aborted"));
    });

    xhr.send(file);
  });
}
