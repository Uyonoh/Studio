"use client";

import { useState, useRef, useCallback } from "react";
import {
  UploadCloud,
  File,
  AlertCircle,
  CheckCircle2,
  Loader2,
  X,
  RotateCcw,
} from "lucide-react";
import { uploadAssetWithProgress, validateUploadFile, type Asset } from "@/hooks/use-assets";
import { toast } from "sonner";

interface AssetUploadZoneProps {
  projectId: string;
  onUploadSuccess: (asset: Asset) => void;
}

interface UploadingFileState {
  id: string;
  file: File;
  progress: number;
  status: "uploading" | "processing" | "success" | "error";
  error?: string;
}

function makeUploadId(): string {
  return `upload-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
}

export function AssetUploadZone({ projectId, onUploadSuccess }: AssetUploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploadQueue, setUploadQueue] = useState<UploadingFileState[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const patchEntry = useCallback(
    (id: string, patch: Partial<UploadingFileState>) => {
      setUploadQueue((prev) => prev.map((item) => (item.id === id ? { ...item, ...patch } : item)));
    },
    []
  );

  const runUpload = useCallback(
    async (uploadId: string, file: File) => {
      try {
        const asset = await uploadAssetWithProgress({
          projectId,
          file,
          onProgress: (percent) => {
            patchEntry(uploadId, {
              progress: percent,
              status: percent >= 100 ? "processing" : "uploading",
            });
          },
        });

        patchEntry(uploadId, { status: "success", progress: 100, error: undefined });
        toast.success(`"${file.name}" uploaded successfully`);
        onUploadSuccess(asset);

        // Auto remove successful entry after 3 seconds
        setTimeout(() => {
          setUploadQueue((prev) => prev.filter((item) => item.id !== uploadId));
        }, 3000);
      } catch (err: any) {
        patchEntry(uploadId, {
          status: "error",
          error: err?.message || "Upload failed",
        });
        toast.error(`Upload failed for "${file.name}": ${err?.message ?? "Upload failed"}`);
      }
    },
    [projectId, onUploadSuccess, patchEntry]
  );

  const processFile = useCallback(
    (file: File) => {
      const uploadId = makeUploadId();
      setUploadQueue((prev) => [
        { id: uploadId, file, progress: 0, status: "uploading" },
        ...prev,
      ]);

      // Fail fast on type/size so the queue shows the reason immediately.
      try {
        validateUploadFile(file);
      } catch (err: any) {
        patchEntry(uploadId, { status: "error", error: err?.message || "Invalid file" });
        toast.error(err?.message || "Invalid file");
        return;
      }

      void runUpload(uploadId, file);
    },
    [patchEntry, runUpload]
  );

  const retryUpload = useCallback(
    (entry: UploadingFileState) => {
      patchEntry(entry.id, { status: "uploading", progress: 0, error: undefined });
      void runUpload(entry.id, entry.file);
    },
    [patchEntry, runUpload]
  );

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    Array.from(files).forEach((file) => processFile(file));
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  return (
    <div className="space-y-4">
      {/* Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            fileInputRef.current?.click();
          }
        }}
        role="button"
        tabIndex={0}
        aria-label="Upload media files"
        className={`group relative border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-200 flex flex-col items-center justify-center gap-3 focus:outline-none focus:ring-2 focus:ring-[#7C5CFF] ${
          isDragging
            ? "border-[#7C5CFF] bg-[#7C5CFF]/10 scale-[0.99]"
            : "border-[#262A35] bg-[#14161C]/50 hover:bg-[#14161C] hover:border-[#7C5CFF]/50"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*,video/*"
          className="hidden"
          onChange={(e) => {
            handleFiles(e.target.files);
            // Allow re-selecting the same file (e.g. after a failed upload).
            e.target.value = "";
          }}
        />

        <div className="w-12 h-12 rounded-2xl bg-[#1B1E26] border border-[#262A35] group-hover:border-[#7C5CFF]/30 flex items-center justify-center text-[#7C5CFF] transition-all group-hover:scale-110">
          <UploadCloud className="w-6 h-6" />
        </div>

        <div>
          <h4 className="text-sm font-semibold text-[#E8EAF0]">
            Drag & drop media here, or <span className="text-[#7C5CFF]">browse</span>
          </h4>
          <p className="text-xs text-[#9AA1B2] mt-1">
            Supports PNG, JPEG, WebP, MP4, WebM up to 200MB.
          </p>
        </div>
      </div>

      {/* Uploads in Progress / Queue */}
      {uploadQueue.length > 0 && (
        <div className="space-y-2" role="status" aria-live="polite">
          {uploadQueue.map((item) => (
            <div
              key={item.id}
              className="p-3 rounded-xl bg-[#14161C] border border-[#262A35] flex items-center justify-between gap-4 text-xs"
            >
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <File className="w-4 h-4 text-[#9AA1B2] shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-[#E8EAF0] truncate max-w-[200px]">
                      {item.file.name}
                    </span>
                    <span className="text-[11px] font-mono text-[#9AA1B2]">
                      {item.status === "uploading" && `${item.progress}%`}
                      {item.status === "processing" && "Processing..."}
                      {item.status === "success" && "Ready"}
                      {item.status === "error" && "Failed"}
                    </span>
                  </div>

                  {/* Progress bar */}
                  <div className="h-1.5 w-full bg-[#1B1E26] rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-200 ${
                        item.status === "error"
                          ? "bg-red-500"
                          : item.status === "success"
                          ? "bg-emerald-500"
                          : "bg-[#7C5CFF]"
                      }`}
                      style={{ width: `${item.progress}%` }}
                    />
                  </div>
                  {item.error && <p className="text-[11px] text-red-400 mt-1">{item.error}</p>}
                </div>
              </div>

              <div className="shrink-0 flex items-center gap-2">
                {(item.status === "uploading" || item.status === "processing") && (
                  <Loader2 className="w-4 h-4 animate-spin text-[#7C5CFF]" />
                )}
                {item.status === "success" && (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                )}
                {item.status === "error" && (
                  <AlertCircle className="w-4 h-4 text-red-400" />
                )}
                {item.status === "error" && (
                  <button
                    type="button"
                    onClick={() => retryUpload(item)}
                    aria-label={`Retry upload ${item.file.name}`}
                    title="Retry upload"
                    className="flex items-center gap-1 px-2 py-1 rounded-lg bg-[#1B1E26] border border-[#262A35] text-[11px] font-medium text-[#E8EAF0] hover:border-[#7C5CFF]/50 transition-colors"
                  >
                    <RotateCcw className="w-3.5 h-3.5 text-[#7C5CFF]" />
                    <span>Retry</span>
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setUploadQueue((prev) => prev.filter((i) => i.id !== item.id))}
                  aria-label={`Dismiss upload ${item.file.name}`}
                  className="p-1 rounded-md text-[#9AA1B2] hover:text-[#E8EAF0] hover:bg-[#1B1E26]"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
