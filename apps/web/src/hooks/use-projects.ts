import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getApiClient } from "@/lib/api";
import { toast } from "sonner";

export interface ProjectPreviewAsset {
  asset_id: string;
  kind: string;
  origin: string;
  thumbnail_url: string | null;
  signed_url: string | null;
}

export interface Project {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  cover_asset_id: string | null;
  previews?: ProjectPreviewAsset[] | null;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export function useProjects(workspaceId?: string | null) {
  return useQuery({
    queryKey: ["projects", workspaceId],
    queryFn: async () => {
      if (!workspaceId) return { items: [] as Project[], next_cursor: null };

      const client = getApiClient();
      const res = await client.GET("/v1/workspaces/{workspace_id}/projects", {
        params: {
          path: { workspace_id: workspaceId },
        },
      });

      if (res.error) {
        throw new Error((res.error as any)?.detail || "Failed to load projects");
      }

      return res.data as { items: Project[]; next_cursor: string | null };
    },
    enabled: !!workspaceId,
  });
}

export function useCreateProject(workspaceId?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      name,
      description,
    }: {
      name: string;
      description?: string | null;
    }) => {
      if (!workspaceId) throw new Error("No active workspace selected");

      const client = getApiClient();
      const res = await client.POST("/v1/workspaces/{workspace_id}/projects", {
        params: {
          path: { workspace_id: workspaceId },
        },
        body: {
          name,
          description: description || null,
        },
      });

      if (res.error) {
        throw new Error((res.error as any)?.detail || "Failed to create project");
      }

      return res.data as Project;
    },
    // Optimistic update
    onMutate: async (newProjectData) => {
      await queryClient.cancelQueries({ queryKey: ["projects", workspaceId] });

      const previousProjects = queryClient.getQueryData<{
        items: Project[];
        next_cursor: string | null;
      }>(["projects", workspaceId]);

      const optimisticProject: Project = {
        id: `optimistic-${Date.now()}`,
        workspace_id: workspaceId || "",
        name: newProjectData.name,
        description: newProjectData.description || null,
        cover_asset_id: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        archived_at: null,
      };

      if (previousProjects) {
        queryClient.setQueryData(["projects", workspaceId], {
          ...previousProjects,
          items: [optimisticProject, ...previousProjects.items],
        });
      } else {
        queryClient.setQueryData(["projects", workspaceId], {
          items: [optimisticProject],
          next_cursor: null,
        });
      }

      return { previousProjects };
    },
    onError: (err, newProject, context) => {
      if (context?.previousProjects) {
        queryClient.setQueryData(["projects", workspaceId], context.previousProjects);
      }
      toast.error(err.message || "Failed to create project");
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", workspaceId] });
    },
    onSuccess: (project) => {
      toast.success(`Project "${project.name}" created!`);
    },
  });
}

export function useUpdateProject(workspaceId?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      projectId,
      name,
      description,
    }: {
      projectId: string;
      name?: string | null;
      description?: string | null;
    }) => {
      const client = getApiClient();
      const res = await client.PATCH("/v1/projects/{project_id}", {
        params: {
          path: { project_id: projectId },
        },
        body: {
          name: name ?? undefined,
          description: description ?? undefined,
        },
      });

      if (res.error) {
        throw new Error((res.error as any)?.detail || "Failed to update project");
      }

      return res.data as Project;
    },
    onSuccess: (updated) => {
      toast.success(`Project "${updated.name}" updated!`);
      queryClient.invalidateQueries({ queryKey: ["projects", workspaceId] });
    },
    onError: (err) => {
      toast.error(err.message || "Failed to update project");
    },
  });
}

export function useArchiveProject(workspaceId?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (projectId: string) => {
      const client = getApiClient();
      const res = await client.DELETE("/v1/projects/{project_id}", {
        params: {
          path: { project_id: projectId },
        },
      });

      if (res.error) {
        throw new Error((res.error as any)?.detail || "Failed to archive project");
      }

      return projectId;
    },
    onSuccess: () => {
      toast.success("Project archived");
      queryClient.invalidateQueries({ queryKey: ["projects", workspaceId] });
    },
    onError: (err) => {
      toast.error(err.message || "Failed to archive project");
    },
  });
}
