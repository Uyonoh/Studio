import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getApiClient } from "@/lib/api";
import { toast } from "sonner";

export interface LineageAssetRef {
  asset_id: string;
  kind: string;
  role: string | null;
  signed_url: string | null;
  thumbnail_url: string | null;
}

export interface LineageSourceJob {
  id: string;
  task_type: string;
  status: string;
  prompt: string | null;
  negative_prompt: string | null;
  params: Record<string, any>;
  model_slug: string | null;
  model_display_name: string | null;
  created_at: string;
}

export interface AssetLineage {
  source_job: LineageSourceJob | null;
  inputs: LineageAssetRef[];
  parent: LineageAssetRef | null;
}

export interface Asset {
  id: string;
  workspace_id: string;
  project_id: string;
  kind: "image" | "video" | string;
  origin: "upload" | "generated" | "derived" | string;
  mime_type: string | null;
  size_bytes: number | null;
  width: number | null;
  height: number | null;
  duration_ms: number | null;
  fps: string | null;
  storage_path: string;
  thumbnail_path: string | null;
  thumbnail_url: string | null;
  signed_url: string | null;
  source_job_id: string | null;
  parent_asset_id: string | null;
  metadata: Record<string, any>;
  created_at: string;
  lineage?: AssetLineage | null;
}

export interface AssetListResponse {
  items: Asset[];
  next_cursor: string | null;
}

export interface AssetFilters {
  kind?: string | null;
  origin?: string | null;
}

export function useAssets(projectId?: string | null, filters?: AssetFilters) {
  return useInfiniteQuery({
    queryKey: ["assets", projectId, filters?.kind, filters?.origin],
    queryFn: async ({ pageParam }) => {
      if (!projectId) return { items: [] as Asset[], next_cursor: null };

      const client = getApiClient();
      const res = await client.GET("/v1/projects/{project_id}/assets", {
        params: {
          path: { project_id: projectId },
          query: {
            cursor: pageParam || undefined,
            kind: filters?.kind || undefined,
            origin: filters?.origin || undefined,
            limit: 24,
          },
        },
      });

      if (res.error) {
        throw new Error((res.error as any)?.detail || "Failed to load assets");
      }

      return res.data as AssetListResponse;
    },
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled: !!projectId,
  });
}

export function useAsset(assetId?: string | null) {
  return useQuery({
    queryKey: ["asset", assetId],
    queryFn: async () => {
      if (!assetId) return null;
      const client = getApiClient();
      const res = await client.GET("/v1/assets/{asset_id}", {
        params: { path: { asset_id: assetId } },
      });
      if (res.error) {
        throw new Error((res.error as any)?.detail || "Failed to load asset details");
      }
      return res.data as unknown as Asset;
    },
    enabled: !!assetId,
  });
}

export function useDeleteAsset(projectId?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (assetId: string) => {
      const client = getApiClient();
      const res = await client.DELETE("/v1/assets/{asset_id}", {
        params: { path: { asset_id: assetId } },
      });
      if (res.error) {
        throw new Error((res.error as any)?.detail || "Failed to delete asset");
      }
      return assetId;
    },
    onSuccess: (deletedId) => {
      toast.success("Asset deleted");
      queryClient.invalidateQueries({ queryKey: ["assets", projectId] });
      queryClient.removeQueries({ queryKey: ["asset", deletedId] });
    },
    onError: (err) => {
      toast.error(err.message || "Failed to delete asset");
    },
  });
}

const MAX_UPLOAD_BYTES = 200 * 1024 * 1024; // 200 MB
const ALLOWED_MIME_PREFIXES = ["image/", "video/"];

/** Validate a file against the client-side type and size limits. */
export function validateUploadFile(file: File): void {
  if (file.size > MAX_UPLOAD_BYTES) {
    throw new Error("File exceeds maximum allowed size (200MB)");
  }
  if (!ALLOWED_MIME_PREFIXES.some((prefix) => file.type.startsWith(prefix))) {
    throw new Error(
      "Only images (PNG, JPEG, WebP, etc.) and videos (MP4, QuickTime, WebM) are allowed"
    );
  }
}

/**
 * Upload a file straight to storage through a signed URL, then confirm it.
 *
 * Retrying a failed upload simply calls this again: a fresh signed URL is
 * requested each time, so expired URLs are never reused.
 */
export async function uploadAssetWithProgress({
  projectId,
  file,
  onProgress,
  onProcessing,
}: {
  projectId: string;
  file: File;
  onProgress?: (progress: number) => void;
  onProcessing?: () => void;
}): Promise<Asset> {
  const client = getApiClient();

  // 1. Client-side checks before spending a round-trip.
  validateUploadFile(file);

  // 2. Request signed upload URL
  let assetId: string | undefined;
  let uploadConfirmed = false;
  try {
    const uploadInitRes = await client.POST("/v1/projects/{project_id}/assets/uploads", {
      params: { path: { project_id: projectId } },
      body: {
        filename: file.name,
        mime_type: file.type || "application/octet-stream",
        size_bytes: file.size,
      },
    });

    if (uploadInitRes.error || !uploadInitRes.data) {
      throw new Error((uploadInitRes.error as any)?.detail || "Failed to initiate asset upload");
    }

    const { asset_id, upload_url } = uploadInitRes.data;
    assetId = asset_id;

    // 3. Direct upload to storage with progress (XHR exposes upload events).
    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", upload_url, true);
      xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");

      if (xhr.upload && onProgress) {
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            const percent = Math.round((e.loaded / e.total) * 100);
            onProgress(percent);
          }
        };
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve();
        } else {
          reject(new Error(`Storage upload failed with HTTP ${xhr.status}`));
        }
      };

      xhr.onerror = () => reject(new Error("Network error during storage upload"));
      xhr.onabort = () => reject(new Error("Upload aborted"));
      xhr.send(file);
    });
    uploadConfirmed = true;

    // 4. Confirm completion with backend (probes metadata, generates a
    //    thumbnail/poster frame, and marks the asset ready).
    onProcessing?.();
    const completeRes = await client.POST("/v1/assets/{asset_id}/complete", {
      params: { path: { asset_id } },
    });

    if (completeRes.error || !completeRes.data) {
      throw new Error((completeRes.error as any)?.detail || "Failed to finalize uploaded asset");
    }

    return completeRes.data as unknown as Asset;
  } catch (err) {
    if (assetId && !uploadConfirmed) {
      // The draft row was created but the object never reached storage; remove
      // it so it cannot linger as an invisible pending asset.
      try {
        await client.DELETE("/v1/assets/{asset_id}", {
          params: { path: { asset_id: assetId } },
        });
      } catch {
        // Best-effort cleanup; the list endpoint hides unfinished uploads anyway.
      }
    }
    throw err;
  }
}
