import { useQuery } from "@tanstack/react-query";
import { getApiClient } from "@/lib/api";

/**
 * Fetch the active workspace's credit balance.
 *
 * Credits live on the workspace (not the user), so the balance follows the
 * currently selected workspace. The backend derives it from the append-only
 * `credit_ledger`, which keeps it correct after reservations, refunds, grants,
 * and purchases.
 */
export function useCreditBalance(workspaceId?: string | null) {
  return useQuery({
    queryKey: ["credits", workspaceId],
    queryFn: async (): Promise<number> => {
      const client = getApiClient();
      const res = await client.GET("/v1/workspaces/{workspace_id}/credits", {
        params: {
          path: { workspace_id: workspaceId as string },
        },
      });

      if (res.error || !res.data) {
        throw new Error(
          (res.error as { detail?: string } | undefined)?.detail ||
            "Failed to load credit balance"
        );
      }

      const balance = Number(res.data.balance);
      return Number.isFinite(balance) ? balance : 0;
    },
    enabled: !!workspaceId,
    staleTime: 15_000,
  });
}
