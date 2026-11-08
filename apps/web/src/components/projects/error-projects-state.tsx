"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";

interface ErrorProjectsStateProps {
  message?: string;
  onRetry: () => void;
}

export function ErrorProjectsState({
  message = "Failed to load projects. Please try again.",
  onRetry,
}: ErrorProjectsStateProps) {
  return (
    <div
      role="alert"
      className="rounded-2xl bg-red-950/20 border border-red-500/30 p-8 text-center flex flex-col items-center justify-center gap-4"
    >
      <div className="w-12 h-12 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 flex items-center justify-center">
        <AlertTriangle className="w-6 h-6" />
      </div>
      <div>
        <h3 className="text-base font-semibold text-[#E8EAF0]">
          Unable to Load Projects
        </h3>
        <p className="text-xs text-[#9AA1B2] mt-1 max-w-md">{message}</p>
      </div>
      <button
        type="button"
        onClick={onRetry}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#1B1E26] hover:bg-[#232732] border border-[#262A35] text-xs font-medium text-[#E8EAF0] transition-colors"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        <span>Try Again</span>
      </button>
    </div>
  );
}
