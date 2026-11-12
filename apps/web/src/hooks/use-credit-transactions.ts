import { useInfiniteQuery } from "@tanstack/react-query";
import { getApiClient } from "@/lib/api";
import { problemMessage } from "@/lib/problem";

export interface CreditTransaction {
  id: number;
  workspace_id: string;
  job_id: string | null;
  delta: string;
  reason: string;
  created_at: string;
  balance_after: string;
  model_name: string | null;
  job_status: string | null;
  prompt: string | null;
}

export interface CreditActivitySummary {
  window_days: number;
  spent: string;
  refunded: string;
  granted: string;
  transactions: number;
}

export interface CreditTransactionsPage {
  items: CreditTransaction[];
  next_before_id: number | null;
  summary: CreditActivitySummary;
}

const PAGE_SIZE = 20;

/**
 * Fetch the active workspace's credit ledger, newest first.
 *
 * Pages are fetched backwards using the ledger id so the running balance on
 * every row remains stable even when new entries arrive while the screen is
 * open.
 */
export function useCreditTransactions(workspaceId?: string | null) {
  return useInfiniteQuery({
    queryKey: ["credit-transactions", workspaceId],
    initialPageParam: null as number | null,
    queryFn: async ({ pageParam }) => {
      const client = getApiClient();
      const res = await client.GET("/v1/workspaces/{workspace_id}/credits/transactions", {
        params: {
          path: { workspace_id: workspaceId as string },
          query: {
            limit: PAGE_SIZE,
            ...(pageParam ? { before_id: pageParam } : {}),
          },
        },
      });

      if (res.error || !res.data) {
        throw new Error(problemMessage(res.error, "Failed to load credit activity"));
      }

      return res.data as unknown as CreditTransactionsPage;
    },
    getNextPageParam: (lastPage) => lastPage.next_before_id ?? undefined,
    enabled: !!workspaceId,
    staleTime: 15_000,
  });
}
