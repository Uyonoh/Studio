"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  X,
  Download,
  Trash2,
  Calendar,
  Layers,
  FileCode,
  HardDrive,
  Sparkles,
  Loader2,
  RefreshCw,
  Copy,
  Check,
  ArrowDownLeft,
  Cpu,
  SlidersHorizontal,
} from "lucide-react";
import { toast } from "sonner";
import { type Asset, type LineageAssetRef, useAsset, useDeleteAsset } from "@/hooks/use-assets";
import { useFocusTrap } from "@/hooks/use-focus-trap";

interface AssetDetailDrawerProps {
  assetId: string | null;
  projectId: string;
  onClose: () => void;
}

function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return "Unknown";
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDuration(ms: number | null | undefined): string {
  if (!ms) return "N/A";
  return `${(ms / 1000).toFixed(1)}s`;
}

function DetailCell({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="p-3 rounded-xl bg-[#0E1015] border border-[#262A35]">
      <div className="flex items-center gap-1.5 text-[11px] text-[#9AA1B2] mb-1">
        {icon}
        <span>{label}</span>
      </div>
      <div className="text-xs font-mono font-medium text-[#E8EAF0] break-words">{value}</div>
    </div>
  );
}

function LineageAssetTile({ asset, label }: { asset: LineageAssetRef; label: string }) {
  const src = asset.thumbnail_url || asset.signed_url;
  return (
    <div className="flex items-center gap-3 p-2.5 rounded-xl bg-[#0E1015] border border-[#262A35]">
      <div className="w-11 h-11 rounded-lg overflow-hidden bg-[#14161C] border border-[#262A35] flex items-center justify-center shrink-0">
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt={label} className="w-full h-full object-cover" loading="lazy" />
        ) : (
          <Layers className="w-4 h-4 text-[#A995FF]" />
        )}
      </div>
      <div className="min-w-0">
        <p className="text-xs font-medium text-[#E8EAF0] truncate">{label}</p>
        <p className="text-[10px] font-mono text-[#9AA1B2] capitalize">
          {asset.role ? `${asset.role.replace(/_/g, " ")} · ` : ""}
          {asset.kind}
        </p>
      </div>
    </div>
  );
}

export function AssetDetailDrawer({ assetId, projectId, onClose }: AssetDetailDrawerProps) {
  const { data: asset, isLoading, isError, refetch } = useAsset(assetId);
  const deleteMutation = useDeleteAsset(projectId);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [copied, setCopied] = useState(false);
  const refreshedMedia = useRef(false);
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Reset per-asset state when a different asset is opened.
    setShowDeleteConfirm(false);
    setCopied(false);
    refreshedMedia.current = false;
  }, [assetId]);

  useFocusTrap(drawerRef, Boolean(assetId), { onEscape: onClose });

  /** Signed URLs expire; refetch once to obtain a fresh one. */
  const handleMediaError = useCallback(() => {
    if (refreshedMedia.current) return;
    refreshedMedia.current = true;
    void refetch();
  }, [refetch]);

  if (!assetId) return null;

  const isVideo = asset?.kind === "video" || asset?.mime_type?.startsWith("video/");
  const displaySrc = asset?.signed_url || asset?.thumbnail_url || "";
  const lineage = asset?.lineage;
  const sourceJob = lineage?.source_job ?? null;
  const prompt = sourceJob?.prompt || asset?.metadata?.prompt || null;
  const negativePrompt = sourceJob?.negative_prompt || asset?.metadata?.negative_prompt || null;
  const modelLabel =
    sourceJob?.model_display_name || sourceJob?.model_slug || asset?.metadata?.model || null;
  const params = (sourceJob?.params || asset?.metadata?.params || {}) as Record<string, unknown>;
  const seed = asset?.metadata?.seed ?? params.seed ?? null;

  const handleDelete = async () => {
    if (!asset) return;
    await deleteMutation.mutateAsync(asset.id);
    setShowDeleteConfirm(false);
    onClose();
  };

  const handleDownload = () => {
    if (!asset?.signed_url) return;
    const a = document.createElement("a");
    a.href = asset.signed_url;
    a.download = asset.metadata?.filename || `${asset.kind}-${asset.id.slice(0, 8)}`;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const handleCopyPrompt = async () => {
    if (!prompt) return;
    try {
      await navigator.clipboard.writeText(prompt);
      setCopied(true);
      toast.success("Prompt copied");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Could not copy prompt");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <div
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="asset-drawer-title"
        tabIndex={-1}
        className="relative w-full max-w-xl bg-[#14161C] border-l border-[#262A35] h-full shadow-2xl z-10 flex flex-col justify-between overflow-y-auto animate-in slide-in-from-right duration-200"
      >
        {/* Header */}
        <div className="p-6 border-b border-[#262A35] flex items-center justify-between sticky top-0 bg-[#14161C]/95 backdrop-blur-md z-20">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="px-2.5 py-0.5 rounded-full bg-[#1B1E26] border border-[#262A35] text-xs font-mono capitalize text-[#A995FF] shrink-0">
              {asset?.kind || "Asset"}
            </span>
            <h3
              id="asset-drawer-title"
              className="text-sm font-semibold text-[#E8EAF0] truncate max-w-[280px]"
            >
              {asset?.metadata?.filename || (asset ? `Asset ${asset.id.slice(0, 8)}` : "Details")}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close drawer"
            className="p-1.5 rounded-lg text-[#9AA1B2] hover:text-[#E8EAF0] hover:bg-[#1B1E26] transition-colors shrink-0"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-6 flex-1">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-20 gap-3 text-[#9AA1B2]">
              <Loader2 className="w-8 h-8 animate-spin text-[#A995FF]" />
              <p className="text-xs">Loading asset details...</p>
            </div>
          ) : isError || !asset ? (
            <div className="rounded-xl bg-red-950/20 border border-red-500/30 p-6 text-center space-y-3">
              <p className="text-xs text-red-400">Failed to load asset details or URL expired.</p>
              <button
                type="button"
                onClick={() => refetch()}
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1B1E26] border border-[#262A35] text-xs text-[#E8EAF0]"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry</span>
              </button>
            </div>
          ) : (
            <>
              {/* Media Preview Box */}
              <div className="rounded-2xl border border-[#262A35] bg-[#0E1015] overflow-hidden flex items-center justify-center max-h-[360px]">
                {isVideo ? (
                  <video
                    src={asset.signed_url || ""}
                    controls
                    autoPlay
                    loop
                    onError={handleMediaError}
                    className="w-full max-h-[360px] object-contain"
                  />
                ) : displaySrc ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={displaySrc}
                    alt={asset.metadata?.filename || "Asset preview"}
                    onError={handleMediaError}
                    className="w-full max-h-[360px] object-contain"
                  />
                ) : (
                  <div className="py-16 text-center text-xs text-[#9AA1B2]">
                    No preview available
                  </div>
                )}
              </div>

              {/* Quick Actions */}
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleDownload}
                  disabled={!asset.signed_url}
                  className="flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-[#1B1E26] hover:bg-[#232732] border border-[#262A35] text-xs font-medium text-[#E8EAF0] transition-colors disabled:opacity-50"
                >
                  <Download className="w-4 h-4 text-[#A995FF]" />
                  <span>Download Original</span>
                </button>
                <button
                  type="button"
                  onClick={() => setShowDeleteConfirm(true)}
                  className="flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-red-950/20 hover:bg-red-900/30 border border-red-500/30 text-xs font-medium text-red-400 transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                  <span>Delete</span>
                </button>
              </div>

              {/* Delete Confirmation Alert */}
              {showDeleteConfirm && (
                <div className="p-4 rounded-xl bg-red-950/30 border border-red-500/40 space-y-3 animate-in fade-in duration-150">
                  <p className="text-xs text-red-200">
                    Are you sure you want to delete this asset? This action will remove it from the
                    project.
                  </p>
                  <div className="flex items-center justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setShowDeleteConfirm(false)}
                      disabled={deleteMutation.isPending}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium text-[#9AA1B2] hover:text-[#E8EAF0] hover:bg-[#1B1E26]"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleDelete}
                      disabled={deleteMutation.isPending}
                      className="px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-semibold flex items-center gap-1.5"
                    >
                      {deleteMutation.isPending && (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      )}
                      <span>Confirm Delete</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Prompt */}
              {prompt && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-[#9AA1B2]">
                      Prompt
                    </h4>
                    <button
                      type="button"
                      onClick={handleCopyPrompt}
                      aria-label="Copy prompt"
                      className="flex items-center gap-1.5 px-2 py-1 rounded-lg text-[11px] text-[#9AA1B2] hover:text-[#E8EAF0] hover:bg-[#1B1E26] transition-colors"
                    >
                      {copied ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                      <span>{copied ? "Copied" : "Copy"}</span>
                    </button>
                  </div>
                  <p className="text-xs text-[#E8EAF0] bg-[#0E1015] border border-[#262A35] p-3 rounded-xl font-mono leading-relaxed">
                    {prompt}
                  </p>
                  {negativePrompt && (
                    <div className="text-[11px] text-[#9AA1B2]">
                      <span className="font-semibold">Negative:</span>{" "}
                      <span className="font-mono">{negativePrompt}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Metadata Grid */}
              <div className="space-y-3">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-[#9AA1B2]">
                  Specifications
                </h4>
                <div className="grid grid-cols-2 gap-3">
                  <DetailCell
                    icon={<HardDrive className="w-3.5 h-3.5 text-[#A995FF]" />}
                    label="File Size"
                    value={formatBytes(asset.size_bytes)}
                  />
                  <DetailCell
                    icon={<Layers className="w-3.5 h-3.5 text-[#A995FF]" />}
                    label="Resolution"
                    value={
                      asset.width && asset.height ? `${asset.width} × ${asset.height} px` : "N/A"
                    }
                  />
                  <DetailCell
                    icon={<FileCode className="w-3.5 h-3.5 text-[#A995FF]" />}
                    label="Format"
                    value={asset.mime_type || "N/A"}
                  />
                  <DetailCell
                    icon={<Calendar className="w-3.5 h-3.5 text-[#A995FF]" />}
                    label="Created"
                    value={new Date(asset.created_at).toLocaleString()}
                  />
                  {isVideo && (
                    <DetailCell
                      icon={<SlidersHorizontal className="w-3.5 h-3.5 text-[#A995FF]" />}
                      label="Duration"
                      value={`${formatDuration(asset.duration_ms)}${
                        asset.fps ? ` · ${Number(asset.fps).toFixed(0)} fps` : ""
                      }`}
                    />
                  )}
                  {modelLabel && (
                    <DetailCell
                      icon={<Cpu className="w-3.5 h-3.5 text-[#A995FF]" />}
                      label="Model"
                      value={modelLabel}
                    />
                  )}
                  {seed !== null && seed !== undefined && (
                    <DetailCell
                      icon={<Sparkles className="w-3.5 h-3.5 text-[#A995FF]" />}
                      label="Seed"
                      value={String(seed)}
                    />
                  )}
                </div>
              </div>

              {/* Lineage */}
              <div className="space-y-3">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-[#9AA1B2]">
                  Origin & Lineage
                </h4>
                <div className="p-4 rounded-xl bg-[#0E1015] border border-[#262A35] space-y-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-[#9AA1B2]">Source Type:</span>
                    <span className="font-mono text-[#E8EAF0] capitalize">{asset.origin}</span>
                  </div>

                  {sourceJob && (
                    <div className="flex items-center justify-between text-xs border-t border-[#262A35]/60 pt-2.5">
                      <span className="text-[#9AA1B2]">Job:</span>
                      <span className="font-mono text-[#E8EAF0] text-[11px]">
                        {sourceJob.task_type.replace(/_/g, " ")} · {sourceJob.status}
                      </span>
                    </div>
                  )}

                  {asset.source_job_id && (
                    <div className="flex items-center justify-between text-xs border-t border-[#262A35]/60 pt-2.5 gap-4">
                      <span className="text-[#9AA1B2] shrink-0">Job ID:</span>
                      <span className="font-mono text-[#A995FF] text-[11px] truncate">
                        {asset.source_job_id}
                      </span>
                    </div>
                  )}

                  {Object.keys(params).length > 0 && (
                    <div className="border-t border-[#262A35]/60 pt-2.5 space-y-2">
                      <span className="text-[11px] text-[#9AA1B2]">Parameters:</span>
                      <div className="flex flex-wrap gap-1.5">
                        {Object.entries(params).map(([key, value]) => (
                          <span
                            key={key}
                            className="px-2 py-0.5 rounded-md bg-[#14161C] border border-[#262A35] text-[10px] font-mono text-[#9AA1B2]"
                          >
                            {key}: {String(value)}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Inputs */}
                {lineage && lineage.inputs.length > 0 && (
                  <div className="space-y-2">
                    <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-[#9AA1B2]">
                      <ArrowDownLeft className="w-3.5 h-3.5 text-[#A995FF]" />
                      <span>Made from</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {lineage.inputs.map((input) => (
                        <LineageAssetTile
                          key={`${input.asset_id}-${input.role ?? "input"}`}
                          asset={input}
                          label={input.role ? input.role.replace(/_/g, " ") : "Input"}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {/* Parent asset (derived media) */}
                {lineage?.parent && (
                  <div className="space-y-2">
                    <div className="text-[11px] uppercase tracking-wider text-[#9AA1B2]">
                      Derived from
                    </div>
                    <LineageAssetTile asset={lineage.parent} label="Parent asset" />
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
