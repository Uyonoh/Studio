import { useMutation } from "@tanstack/react-query";
import { getApiClient } from "@/lib/api";
import { problemMessage } from "@/lib/problem";

export interface UpdatedWorkspace {
  id: string;
  name: string;
  owner_id?: string;
}

/** Rename a workspace the signed-in user owns or administers. */
export function useUpdateWorkspace() {
  return useMutation({
    mutationFn: async ({
      workspaceId,
      name,
    }: {
      workspaceId: string;
      name: string;
    }): Promise<UpdatedWorkspace> => {
      const client = getApiClient();
      const res = await client.PATCH("/v1/workspaces/{workspace_id}", {
        params: { path: { workspace_id: workspaceId } },
        body: { name },
      });

      if (res.error || !res.data) {
        throw new Error(problemMessage(res.error, "Failed to update workspace"));
      }

      return res.data as unknown as UpdatedWorkspace;
    },
  });
}
