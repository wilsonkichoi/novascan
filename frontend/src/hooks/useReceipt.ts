import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getReceipt,
  deleteReceipt,
  updateReceipt,
  type ReceiptDetail,
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
