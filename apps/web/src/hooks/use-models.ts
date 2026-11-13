import { useQuery } from "@tanstack/react-query";
import { getApiClient } from "@/lib/api";
import { problemMessage } from "@/lib/problem";
import type { ModelInputSchema } from "@/lib/generation-params";

export type TaskType =
  | "text_to_image"
  | "image_to_image"
  | "text_to_video"
  | "image_to_video";

export interface ModelInputCapability {
  role: string;
  kind: string;
  required: boolean;
  max_count: number;
  label: string;
}

export interface StudioModel {
  id: string;
  slug: string;
  display_name: string;
  task_type: TaskType | string;
  provider_id: string;
  input_schema: ModelInputSchema;
  default_params: Record<string, string | number | boolean | null>;
  cost_credits: string;
  required_input_roles: string[];
  input_capabilities?: ModelInputCapability[];
}

/** Fetch enabled models, optionally filtered to a single task type. */
export function useModels(taskType?: string | null) {
  return useQuery({
    queryKey: ["models", taskType ?? "all"],
    queryFn: async () => {
      const client = getApiClient();
      const res = await client.GET("/v1/models", {
        params: { query: taskType ? { task_type: taskType } : {} },
      });

      if (res.error) {
        throw new Error(problemMessage(res.error, "Failed to load models"));
      }

      return (res.data ?? []) as unknown as StudioModel[];
    },
    staleTime: 60_000,
  });
}
