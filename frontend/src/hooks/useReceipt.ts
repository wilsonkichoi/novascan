import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getReceipt,
  deleteReceipt,
  type ReceiptDetail,
} from "@/api/receipts";

export function useReceipt(id: string) {
  return useQuery<ReceiptDetail>({
    queryKey: ["receipt", id],
    queryFn: () => getReceipt(id),
    enabled: Boolean(id),
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
