"use client";

import { FolderPlus, Plus } from "lucide-react";

interface EmptyProjectsStateProps {
  onCreateClick: () => void;
}

export function EmptyProjectsState({ onCreateClick }: EmptyProjectsStateProps) {
  return (
    <div className="relative rounded-2xl bg-[#14161C] border border-[#262A35] overflow-hidden py-16 px-6 sm:px-12 flex flex-col items-center justify-center text-center shadow-card">
      {/* Background glow */}
      <div className="absolute -top-32 left-1/2 -translate-x-1/2 w-96 h-96 bg-[#6C4CE8]/10 rounded-full blur-3xl pointer-events-none" />

      {/* Center Icon */}
      <div className="relative mb-6">
        <div className="w-20 h-20 rounded-2xl bg-[#1B1E26] border border-[#262A35] flex items-center justify-center shadow-inner relative group">
          <FolderPlus className="w-10 h-10 text-[#A995FF]" />
        </div>
      </div>

      <div className="max-w-md flex flex-col items-center gap-1.5 mb-8">
        <h2 className="text-xl font-bold text-[#E8EAF0]">
          Your creative workspace is ready
        </h2>
        <p className="text-sm text-[#9AA1B2]">
          Create your first project to start generating images, videos, and multi-modal media assets.
        </p>
      </div>

      <button
        type="button"
        onClick={onCreateClick}
        className="group relative inline-flex items-center gap-2 h-11 px-6 rounded-xl bg-[#6C4CE8] hover:bg-[#5B3FD6] text-white font-medium text-sm shadow-[0_0_24px_rgba(124,92,255,0.25)] transition-all transform active:scale-95"
      >
        <Plus className="w-4 h-4 transition-transform group-hover:rotate-90" />
        <span>Create your first project</span>
      </button>
    </div>
  );
}
