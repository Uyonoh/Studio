"use client";

import { useEffect } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { type Project } from "@/hooks/use-projects";

interface ArchiveProjectDialogProps {
  project: Project | null;
  isOpen: boolean;
  isLoading: boolean;
  onClose: () => void;
  onConfirm: (projectId: string) => void;
}

export function ArchiveProjectDialog({
  project,
  isOpen,
  isLoading,
  onClose,
  onConfirm,
}: ArchiveProjectDialogProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !project) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="fixed inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="archive-project-title"
        className="relative w-full max-w-md bg-[#14161C] border border-[#262A35] rounded-2xl p-6 shadow-card z-10 animate-in fade-in zoom-in-95 duration-150"
      >
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 flex items-center justify-center flex-shrink-0">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div className="space-y-1.5 flex-1">
            <h2
              id="archive-project-title"
              className="text-base font-semibold text-[#E8EAF0]"
            >
              Archive Project
            </h2>
            <p className="text-xs text-[#9AA1B2] leading-relaxed">
              Are you sure you want to archive{" "}
              <strong className="text-[#E8EAF0]">{project.name}</strong>? It will
              no longer appear in your active project list.
            </p>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 pt-6">
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            className="px-4 py-2 rounded-xl text-xs font-medium text-[#9AA1B2] hover:text-[#E8EAF0] hover:bg-[#1B1E26] transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm(project.id)}
            disabled={isLoading}
            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-white text-xs font-semibold shadow-[0_0_16px_rgba(220,38,38,0.25)] transition-all disabled:opacity-50"
          >
            {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
            <span>Archive Project</span>
          </button>
        </div>
      </div>
    </div>
  );
}
