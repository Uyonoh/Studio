"use client";

import { useState } from "react";
import { Check, Image as ImageIcon, Loader2, UploadCloud, X } from "lucide-react";
import { useAssets, type Asset } from "@/hooks/use-assets";
import { AssetUploadZone } from "@/components/assets/asset-upload-zone";

interface ComposerImagePickerProps {
  projectId: string;
  values: Asset[];
  onChange: (assets: Asset[]) => void;
  /** Maximum number of assets this slot accepts. */
  max?: number;
  /** Asset kind shown in the library / upload tab. */
  kind?: "image" | "video" | string;
  /** Visible field label, e.g. "Source images" or "Last frame". */
  label?: string;
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
 * Pick media for a model input slot, either from the project library or by
 * uploading a new file. Slots with `max > 1` support ordered multi-selection.
 */
export function ComposerImagePicker({
  projectId,
  values,
  onChange,
  max = 1,
  kind = "image",
  label = "Source image",
  error,
}: ComposerImagePickerProps) {
  const [tab, setTab] = useState<"library" | "upload">("library");
  const { data, isLoading, isError } = useAssets(projectId, { kind });
  const assets = data?.pages.flatMap((page) => page.items) ?? [];
  const atLimit = values.length >= max;

  function toggle(asset: Asset) {
    if (values.some((selected) => selected.id === asset.id)) {
      onChange(values.filter((selected) => selected.id !== asset.id));
      return;
    }
    if (atLimit) return;
    onChange([...values, asset]);
  }

  function remove(assetId: string) {
    onChange(values.filter((asset) => asset.id !== assetId));
  }

  function addUploaded(asset: Asset) {
    if (values.some((selected) => selected.id === asset.id)) {
      setTab("library");
      return;
    }
    if (atLimit) return;
    onChange([...values, asset]);
    setTab("library");
  }

  return (
    <div role="group" aria-label={label} className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-medium text-[#C7CBD6]">{label}</span>
        <div className="flex items-center gap-2">
          {max > 1 && (
            <span className="text-[11px] tabular-nums text-[#9AA1B2]">
              {values.length}/{max}
            </span>
          )}
          <div className="flex items-center bg-[#14161C] border border-[#262A35] rounded-lg p-0.5">
            <button
              type="button"
              onClick={() => setTab("library")}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                tab === "library" ? "bg-[#6C4CE8] text-white" : "text-[#9AA1B2] hover:text-[#E8EAF0]"
              }`}
            >
              From library
            </button>
            <button
              type="button"
              onClick={() => setTab("upload")}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                tab === "upload" ? "bg-[#6C4CE8] text-white" : "text-[#9AA1B2] hover:text-[#E8EAF0]"
              }`}
            >
              Upload new
            </button>
          </div>
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
              Loading {kind === "image" ? "images" : "media"}…
            </div>
          )}

          {isError && (
            <p className="text-xs text-red-400">
              Could not load project {kind === "image" ? "images" : "media"}. Upload one instead.
            </p>
          )}

          {!isLoading && !isError && assets.length === 0 && (
            <p className="text-xs text-[#9AA1B2]">
              No {kind === "image" ? "images" : "media"} in this project yet. Upload one to get
              started.
            </p>
          )}

          {assets.length > 0 && (
            <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
              {assets.map((asset) => {
                const name = assetFilename(asset);
                const selectedIndex = values.findIndex((selected) => selected.id === asset.id);
                const selected = selectedIndex >= 0;
                const disabled = !selected && atLimit;
                const src = asset.thumbnail_url || asset.signed_url || "";
                return (
                  <button
                    key={asset.id}
                    type="button"
                    aria-label={`Use ${name}`}
                    aria-pressed={selected}
                    title={disabled ? `Maximum of ${max} selected` : name}
                    disabled={disabled}
                    onClick={() => toggle(asset)}
                    className={`relative aspect-square rounded-lg overflow-hidden border transition-all focus:outline-none focus:ring-2 focus:ring-[#7C5CFF] disabled:cursor-not-allowed disabled:opacity-40 ${
                      selected
                        ? "border-[#7C5CFF] ring-2 ring-[#7C5CFF]/40"
                        : "border-[#262A35] hover:border-[#7C5CFF]/60"
                    }`}
                  >
                    {src ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={src} alt={name} className="w-full h-full object-cover" />
                    ) : (
                      <span className="flex w-full h-full items-center justify-center text-[#9AA1B2]">
                        <ImageIcon className="w-5 h-5" />
                      </span>
                    )}
                    {selected && (
                      <span className="absolute top-1 right-1 flex items-center justify-center rounded-full bg-[#6C4CE8] text-white min-w-4 h-4 px-1 text-[10px] font-semibold">
                        {max > 1 ? selectedIndex + 1 : <Check className="w-3 h-3" />}
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
          <AssetUploadZone projectId={projectId} onUploadSuccess={addUploaded} />
        </div>
      )}

      {values.length > 0 && (
        <div className="space-y-2">
          {values.map((asset, index) => (
            <div
              key={asset.id}
              className="flex items-center justify-between gap-3 rounded-xl border border-[#7C5CFF]/40 bg-[#6C4CE8]/5 px-3 py-2"
            >
              <div className="flex items-center gap-2 min-w-0">
                <UploadCloud className="w-4 h-4 text-[#A995FF] shrink-0" />
                {max > 1 && (
                  <span className="text-[10px] font-semibold text-[#A995FF] tabular-nums">
                    {index + 1}
                  </span>
                )}
                <span className="text-xs text-[#E8EAF0] truncate">{assetFilename(asset)}</span>
              </div>
              <button
                type="button"
                onClick={() => remove(asset.id)}
                aria-label={max > 1 ? `Remove ${assetFilename(asset)}` : "Clear selected image"}
                className="p-1 rounded-md text-[#9AA1B2] hover:text-[#E8EAF0] hover:bg-[#1B1E26]"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
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
