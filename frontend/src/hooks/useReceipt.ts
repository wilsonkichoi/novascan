import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getReceipt,
  deleteReceipt,
  updateItems,
  updateReceipt,
  reprocessReceipt,
  type ReceiptDetail,
  type LineItemInput,
  type ReceiptUpdatePayload,
} from "@/api/receipts";

export function useReceipt(id: string) {
  return useQuery<ReceiptDetail>({
    queryKey: ["receipt", id],
    queryFn: () => getReceipt(id),
    enabled: Boolean(id),
  });
}

export function useUpdateReceipt(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ReceiptUpdatePayload) => updateReceipt(id, data),
    onSuccess: (updatedReceipt) => {
      queryClient.setQueryData(["receipt", id], updatedReceipt);
      void queryClient.invalidateQueries({ queryKey: ["receipts"] });
    },
  });
}

export function useDeleteReceipt() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => deleteReceipt(id),
    onSuccess: (_data, id) => {
      queryClient.removeQueries({ queryKey: ["receipt", id] });
      void queryClient.invalidateQueries({ queryKey: ["receipts"] });
    },
  });
}

export function useReprocessReceipt(receiptId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => reprocessReceipt(receiptId),
    onSuccess: (updatedReceipt) => {
      queryClient.setQueryData(["receipt", receiptId], updatedReceipt);
      void queryClient.invalidateQueries({ queryKey: ["receipts"] });
      void queryClient.invalidateQueries({ queryKey: ["pipeline-results", receiptId] });
    },
  });
}

export function useUpdateItems(receiptId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (items: LineItemInput[]) => updateItems(receiptId, items),
    onMutate: async (newItems) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ["receipt", receiptId] });

      // Snapshot current data for rollback
      const previous = queryClient.getQueryData<ReceiptDetail>([
        "receipt",
        receiptId,
      ]);

      // Optimistically update the cache
      if (previous) {
        queryClient.setQueryData<ReceiptDetail>(
          ["receipt", receiptId],
          {
            ...previous,
            lineItems: newItems.map((item) => ({
              sortOrder: item.sortOrder,
              name: item.name,
              quantity: item.quantity,
              unitPrice: item.unitPrice,
              totalPrice: item.totalPrice,
              subcategory: item.subcategory ?? null,
              subcategoryDisplay: null,
            })),
          },
        );
      }

      return { previous };
    },
    onError: (_err, _newItems, context) => {
      // Rollback on failure
      if (context?.previous) {
        queryClient.setQueryData(
          ["receipt", receiptId],
          context.previous,
        );
      }
    },
    onSettled: () => {
      // Refetch to get server truth
      void queryClient.invalidateQueries({ queryKey: ["receipt", receiptId] });
    },
  });
}
