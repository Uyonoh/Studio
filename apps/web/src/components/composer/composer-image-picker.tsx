"use client";

import { useState } from "react";
import { Check, Image as ImageIcon, Loader2, UploadCloud, X } from "lucide-react";
import { useAssets, type Asset } from "@/hooks/use-assets";
import { AssetUploadZone } from "@/components/assets/asset-upload-zone";

interface ComposerImagePickerProps {
  projectId: string;
  value: Asset | null;
  onChange: (asset: Asset | null) => void;
  error?: string;
}

/** Best-effort display name for an asset. */
export function assetFilename(asset: Asset): string {
  const filename = asset.metadata?.filename;
  if (typeof filename === "string" && filename.trim()) return filename;
  const path = asset.storage_path ?? "";
  return path.split("/").pop() || "asset";
}

/**
 * Pick the source image for image-to-image / image-to-video flows, either from
 * the project library or by uploading a new file.
 */
export function ComposerImagePicker({
  projectId,
  value,
  onChange,
  error,
}: ComposerImagePickerProps) {
  const [tab, setTab] = useState<"library" | "upload">("library");
  const { data, isLoading, isError } = useAssets(projectId, { kind: "image" });
  const assets = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-medium text-[#C7CBD6]">Source image</span>
        <div className="flex items-center bg-[#14161C] border border-[#262A35] rounded-lg p-0.5">
          <button
            type="button"
            onClick={() => setTab("library")}
            className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
              tab === "library" ? "bg-[#7C5CFF] text-white" : "text-[#9AA1B2] hover:text-[#E8EAF0]"
            }`}
          >
            From library
          </button>
          <button
            type="button"
            onClick={() => setTab("upload")}
            className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
              tab === "upload" ? "bg-[#7C5CFF] text-white" : "text-[#9AA1B2] hover:text-[#E8EAF0]"
            }`}
          >
            Upload new
          </button>
        </div>
      </div>

      {tab === "library" && (
        <div
          className={`rounded-xl border p-3 ${
            error ? "border-red-500/60 bg-red-500/5" : "border-[#262A35] bg-[#0F1117]"
          }`}
        >
          {isLoading && (
            <div className="flex items-center gap-2 text-xs text-[#9AA1B2]">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading images…
            </div>
          )}

          {isError && (
            <p className="text-xs text-red-400">
              Could not load project images. Upload one instead.
            </p>
          )}

          {!isLoading && !isError && assets.length === 0 && (
            <p className="text-xs text-[#9AA1B2]">
              No images in this project yet. Upload one to get started.
            </p>
          )}

          {assets.length > 0 && (
            <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
              {assets.map((asset) => {
                const name = assetFilename(asset);
                const selected = value?.id === asset.id;
                const src = asset.thumbnail_url || asset.signed_url || "";
                return (
                  <button
                    key={asset.id}
                    type="button"
                    aria-label={`Use ${name}`}
                    aria-pressed={selected}
                    title={name}
                    onClick={() => onChange(selected ? null : asset)}
                    className={`relative aspect-square rounded-lg overflow-hidden border transition-all focus:outline-none focus:ring-2 focus:ring-[#7C5CFF] ${
                      selected
                        ? "border-[#7C5CFF] ring-2 ring-[#7C5CFF]/40"
                        : "border-[#262A35] hover:border-[#7C5CFF]/60"
                    }`}
                  >
                    {src ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={src} alt={name} className="w-full h-full object-cover" />
                    ) : (
                      <span className="flex w-full h-full items-center justify-center text-[#6B7280]">
                        <ImageIcon className="w-5 h-5" />
                      </span>
                    )}
                    {selected && (
                      <span className="absolute top-1 right-1 rounded-full bg-[#7C5CFF] p-0.5 text-white">
                        <Check className="w-3 h-3" />
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      {tab === "upload" && (
        <div className="rounded-xl border border-[#262A35] bg-[#0F1117] p-3">
          <AssetUploadZone
            projectId={projectId}
            onUploadSuccess={(asset) => {
              onChange(asset);
              setTab("library");
            }}
          />
        </div>
      )}

      {value && (
        <div className="flex items-center justify-between gap-3 rounded-xl border border-[#7C5CFF]/40 bg-[#7C5CFF]/5 px-3 py-2">
          <div className="flex items-center gap-2 min-w-0">
            <UploadCloud className="w-4 h-4 text-[#7C5CFF] shrink-0" />
            <span className="text-xs text-[#E8EAF0] truncate">{assetFilename(value)}</span>
          </div>
          <button
            type="button"
            onClick={() => onChange(null)}
            aria-label="Clear selected image"
            className="p-1 rounded-md text-[#9AA1B2] hover:text-[#E8EAF0] hover:bg-[#1B1E26]"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {error && (
        <p role="alert" className="text-[11px] text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}
