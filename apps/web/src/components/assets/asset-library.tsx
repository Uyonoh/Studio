"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { type Asset, useAssets } from "@/hooks/use-assets";
import { AssetCard } from "./asset-card";
import { AssetUploadZone } from "./asset-upload-zone";
import { AssetDetailDrawer } from "./asset-detail-drawer";
import {
  Image as ImageIcon,
  Video,
  Filter,
  Loader2,
  Sparkles,
  Layers,
  UploadCloud,
} from "lucide-react";

interface AssetLibraryProps {
  projectId: string;
}

export function AssetLibrary({ projectId }: AssetLibraryProps) {
  const [kindFilter, setKindFilter] = useState<string | null>(null);
  const [originFilter, setOriginFilter] = useState<string | null>(null);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const refreshedAssetIds = useRef<Set<string>>(new Set());

  const {
    data,
    isLoading,
    isError,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    refetch,
  } = useAssets(projectId, {
    kind: kindFilter,
    origin: originFilter,
  });

  const allAssets = data?.pages.flatMap((page) => page.items) || [];

  // Infinite scroll: fetch the next cursor page when the sentinel scrolls in.
  useEffect(() => {
    const node = loadMoreRef.current;
    if (!node || !hasNextPage) return;
    if (typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && !isFetchingNextPage) {
          void fetchNextPage();
        }
      },
      { rootMargin: "240px 0px" }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  /**
   * Signed URLs are short-lived. When media fails to load we refetch the list
   * once per asset to pick up a freshly signed URL instead of showing a
   * broken tile forever.
   */
  const handleMediaError = useCallback(
    (asset: Asset) => {
      if (refreshedAssetIds.current.has(asset.id)) return;
      refreshedAssetIds.current.add(asset.id);
      void refetch();
    },
    [refetch]
  );

  return (
    <div className="space-y-6">
      {/* Action Bar / Filters */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        {/* Filters */}
        <div className="flex items-center flex-wrap gap-2">
          {/* Kind Filter buttons */}
          <div className="flex items-center bg-[#14161C] border border-[#262A35] rounded-xl p-1">
            <button
              type="button"
              onClick={() => setKindFilter(null)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                kindFilter === null
                  ? "bg-[#6C4CE8] text-white"
                  : "text-[#9AA1B2] hover:text-[#E8EAF0]"
              }`}
            >
              All Types
            </button>
            <button
              type="button"
              onClick={() => setKindFilter("image")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                kindFilter === "image"
                  ? "bg-[#6C4CE8] text-white"
                  : "text-[#9AA1B2] hover:text-[#E8EAF0]"
              }`}
            >
              <ImageIcon className="w-3.5 h-3.5" />
              <span>Images</span>
            </button>
            <button
              type="button"
              onClick={() => setKindFilter("video")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                kindFilter === "video"
                  ? "bg-[#6C4CE8] text-white"
                  : "text-[#9AA1B2] hover:text-[#E8EAF0]"
              }`}
            >
              <Video className="w-3.5 h-3.5" />
              <span>Videos</span>
            </button>
          </div>

          {/* Origin Filter */}
          <div className="flex items-center bg-[#14161C] border border-[#262A35] rounded-xl p-1">
            <button
              type="button"
              onClick={() => setOriginFilter(null)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                originFilter === null
                  ? "bg-[#1B1E26] text-[#E8EAF0] border border-[#262A35]"
                  : "text-[#9AA1B2] hover:text-[#E8EAF0]"
              }`}
            >
              All Origins
            </button>
            <button
              type="button"
              onClick={() => setOriginFilter("generation")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                originFilter === "generation"
                  ? "bg-[#1B1E26] text-[#A995FF] border border-[#7C5CFF]/30"
                  : "text-[#9AA1B2] hover:text-[#E8EAF0]"
              }`}
            >
              <Sparkles className="w-3 h-3" />
              <span>Generated</span>
            </button>
            <button
              type="button"
              onClick={() => setOriginFilter("upload")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                originFilter === "upload"
                  ? "bg-[#1B1E26] text-[#A995FF] border border-[#7C5CFF]/30"
                  : "text-[#9AA1B2] hover:text-[#E8EAF0]"
              }`}
            >
              <UploadCloud className="w-3 h-3" />
              <span>Uploaded</span>
            </button>
          </div>
        </div>

        {/* Upload Toggle Button */}
        <button
          type="button"
          onClick={() => setIsUploadOpen((prev) => !prev)}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#6C4CE8] hover:bg-[#5B3FD6] text-white text-xs font-semibold shadow-[0_0_16px_rgba(124,92,255,0.25)] transition-all"
        >
          <UploadCloud className="w-4 h-4" />
          <span>{isUploadOpen ? "Hide Upload" : "Upload Assets"}</span>
        </button>
      </div>

      {/* Upload Zone Collapse */}
      {isUploadOpen && (
        <div className="p-6 rounded-2xl bg-[#14161C] border border-[#262A35] animate-in fade-in duration-200">
          <AssetUploadZone
            projectId={projectId}
            onUploadSuccess={() => {
              void refetch();
            }}
          />
        </div>
      )}

      {/* Assets Grid */}
      {isLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {Array.from({ length: 12 }).map((_, i) => (
            <div
              key={i}
              className="aspect-square rounded-2xl bg-[#14161C] border border-[#262A35] animate-pulse"
            />
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-2xl bg-red-950/20 border border-red-500/30 p-12 text-center space-y-3">
          <p className="text-sm text-red-400">
            {(error as Error)?.message || "Failed to load project assets."}
          </p>
          <button
            type="button"
            onClick={() => refetch()}
            className="px-4 py-2 rounded-xl bg-[#1B1E26] border border-[#262A35] text-xs font-medium text-[#E8EAF0]"
          >
            Try Again
          </button>
        </div>
      ) : allAssets.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-[#262A35] bg-[#14161C]/50 p-16 text-center flex flex-col items-center justify-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-[#1B1E26] border border-[#262A35] flex items-center justify-center text-[#A995FF]">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-[#E8EAF0]">No assets yet</h3>
            <p className="text-xs text-[#9AA1B2] mt-1">
              Upload images or videos, or generate content using the Composer.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setIsUploadOpen(true)}
            className="mt-2 px-4 py-2 rounded-xl bg-[#6C4CE8] text-white text-xs font-semibold"
          >
            Upload First Asset
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {allAssets.map((asset) => (
              <AssetCard
                key={asset.id}
                asset={asset}
                onClick={(a) => setSelectedAssetId(a.id)}
                onMediaError={handleMediaError}
              />
            ))}
          </div>

          {/* Infinite scroll sentinel + keyboard-accessible fallback */}
          {hasNextPage && (
            <div ref={loadMoreRef} className="flex justify-center pt-4">
              <button
                type="button"
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
                className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-[#14161C] border border-[#262A35] hover:border-[#383E4E] text-xs font-medium text-[#E8EAF0] transition-colors disabled:opacity-50"
              >
                {isFetchingNextPage ? (
                  <Loader2 className="w-4 h-4 animate-spin text-[#A995FF]" />
                ) : null}
                <span>{isFetchingNextPage ? "Loading more..." : "Load More Assets"}</span>
              </button>
            </div>
          )}
        </div>
      )}

      {/* Asset Detail Drawer */}
      <AssetDetailDrawer
        assetId={selectedAssetId}
        projectId={projectId}
        onClose={() => setSelectedAssetId(null)}
      />
    </div>
  );
}
