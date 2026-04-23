import { getValidIdToken } from "@/lib/auth";

const API_URL = import.meta.env.VITE_API_URL ?? "";

interface ApiError {
  error: { code: string; message: string };
}

// --- Category types ---

export interface SubcategoryItem {
  slug: string;
  displayName: string;
}

export interface CategoryItem {
  slug: string;
  displayName: string;
  isCustom: boolean;
  parentCategory?: string | null;
  subcategories: SubcategoryItem[];
}

export interface CategoriesResponse {
  categories: CategoryItem[];
}

export interface CreateCategoryRequest {
  displayName: string;
  parentCategory?: string | null;
}

export interface CreateCategoryResponse {
  slug: string;
  displayName: string;
  parentCategory: string | null;
  isCustom: boolean;
}

// --- Pipeline results types ---

export interface PipelineLineItem {
  name: string;
  quantity: number;
  unitPrice: number;
  totalPrice: number;
  subcategory?: string | null;
}

export interface PipelineExtractedData {
  merchant?: { name: string; address?: string; phone?: string } | null;
  receiptDate?: string | null;
  lineItems?: PipelineLineItem[];
  subtotal?: number | null;
  tax?: number | null;
  tip?: number | null;
  total?: number | null;
  category?: string | null;
  subcategory?: string | null;
  paymentMethod?: string | null;
  confidence?: number | null;
  currency?: string | null;
}

export interface PipelineResult {
  extractedData: PipelineExtractedData | null;
  confidence: number | null;
  rankingScore: number | null;
  processingTimeMs: number;
  modelId: string;
  createdAt: string;
  inputTokens: number;
  outputTokens: number;
  textractPages: number;
  costUsd: number | null;
}

export interface PipelineResultsResponse {
  receiptId: string;
  usedFallback: boolean;
  rankingWinner: "ocr-ai" | "ai-multimodal" | null;
  results: {
    "ocr-ai"?: PipelineResult;
    "ai-multimodal"?: PipelineResult;
  };
}

// --- Category API functions ---

export async function fetchCategories(): Promise<CategoriesResponse> {
  const token = await getValidIdToken();
  if (!token) throw new Error("Not authenticated");

  const res = await fetch(`${API_URL}/api/categories`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch categories (${res.status})`);
  }

  return (await res.json()) as CategoriesResponse;
}

export async function createCategory(
  data: CreateCategoryRequest,
): Promise<CreateCategoryResponse> {
  const token = await getValidIdToken();
  if (!token) throw new Error("Not authenticated");

  const res = await fetch(`${API_URL}/api/categories`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    const errorBody = (await res.json().catch(() => null)) as ApiError | null;
    const message =
      errorBody?.error?.message ?? `Failed to create category (${res.status})`;
    throw new Error(message);
  }

  return (await res.json()) as CreateCategoryResponse;
}

export async function deleteCategory(slug: string): Promise<void> {
  const token = await getValidIdToken();
  if (!token) throw new Error("Not authenticated");

  const res = await fetch(
    `${API_URL}/api/categories/${encodeURIComponent(slug)}`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    },
  );

  if (!res.ok) {
    const errorBody = (await res.json().catch(() => null)) as ApiError | null;
    const message =
      errorBody?.error?.message ?? `Failed to delete category (${res.status})`;
    throw new Error(message);
  }
}

// --- Pipeline results API function ---

export async function fetchPipelineResults(
  receiptId: string,
): Promise<PipelineResultsResponse> {
  const token = await getValidIdToken();
  if (!token) throw new Error("Not authenticated");

  const res = await fetch(
    `${API_URL}/api/receipts/${encodeURIComponent(receiptId)}/pipeline-results`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  );

  if (!res.ok) {
    const errorBody = (await res.json().catch(() => null)) as ApiError | null;
    const message =
      errorBody?.error?.message ??
      `Failed to fetch pipeline results (${res.status})`;
    throw new Error(message);
  }

  return (await res.json()) as PipelineResultsResponse;
}
