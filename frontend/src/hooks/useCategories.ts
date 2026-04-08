import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchCategories,
  createCategory,
  deleteCategory,
  fetchPipelineResults,
  type CategoriesResponse,
  type CreateCategoryRequest,
  type PipelineResultsResponse,
} from "@/api/categories";

export function useCategories() {
  return useQuery<CategoriesResponse>({
    queryKey: ["categories"],
    queryFn: fetchCategories,
  });
}

export function useCreateCategory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateCategoryRequest) => createCategory(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["categories"] });
    },
  });
}

export function useDeleteCategory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (slug: string) => deleteCategory(slug),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["categories"] });
    },
  });
}

export function usePipelineResults(receiptId: string, enabled: boolean) {
  return useQuery<PipelineResultsResponse>({
    queryKey: ["pipeline-results", receiptId],
    queryFn: () => fetchPipelineResults(receiptId),
    enabled: Boolean(receiptId) && enabled,
  });
}
