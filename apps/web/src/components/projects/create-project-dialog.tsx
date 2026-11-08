"use client";

import { useState, useEffect, useRef } from "react";
import { X, Loader2, Sparkles } from "lucide-react";
import { useFocusTrap } from "@/hooks/use-focus-trap";

interface CreateProjectDialogProps {
  isOpen: boolean;
  isLoading: boolean;
  onClose: () => void;
  onSubmit: (data: { name: string; description: string }) => void;
}

export function CreateProjectDialog({
  isOpen,
  isLoading,
  onClose,
  onSubmit,
}: CreateProjectDialogProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
    }
  }, [isOpen]);

  useFocusTrap(dialogRef, isOpen, { initialFocusRef: inputRef, onEscape: onClose });

  if (!isOpen) return null;

  const handleClose = () => {
    setName("");
    setDescription("");
    setError(null);
    onClose();
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Project name is required");
      return;
    }
    setError(null);
    onSubmit({ name: trimmed, description: description.trim() });
    setName("");
    setDescription("");
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Dialog card */}
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-project-title"
        tabIndex={-1}
        className="relative w-full max-w-lg bg-[#14161C] border border-[#262A35] rounded-2xl p-6 shadow-card z-10 animate-in fade-in zoom-in-95 duration-150"
      >
        <div className="flex items-center justify-between pb-4 border-b border-[#262A35]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#1B1E26] border border-[#262A35] flex items-center justify-center text-[#A995FF]">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h2
                id="create-project-title"
                className="text-base font-semibold text-[#E8EAF0]"
              >
                Create New Project
              </h2>
              <p className="text-xs text-[#9AA1B2]">
                A container for your media assets and generation jobs.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1 rounded-lg text-[#9AA1B2] hover:text-[#E8EAF0] hover:bg-[#1B1E26] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 pt-4">
          <div className="space-y-1.5">
            <label
              htmlFor="project-name"
              className="block text-xs font-medium text-[#9AA1B2]"
            >
              Project Name <span className="text-red-400">*</span>
            </label>
            <input
              ref={inputRef}
              id="project-name"
              name="name"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Cyberpunk Teaser Campaign"
              className="w-full px-3.5 py-2.5 rounded-xl bg-[#0B0C10] border border-[#262A35] text-[#E8EAF0] placeholder-[#9AA1B2]/50 text-sm focus:outline-none focus:border-[#7C5CFF] focus:ring-1 focus:ring-[#7C5CFF] transition-all"
            />
            {error && <p className="text-xs text-red-400 mt-1">{error}</p>}
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="project-description"
              className="block text-xs font-medium text-[#9AA1B2]"
            >
              Description (Optional)
            </label>
            <textarea
              id="project-description"
              name="description"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What are you building in this project?"
              className="w-full px-3.5 py-2.5 rounded-xl bg-[#0B0C10] border border-[#262A35] text-[#E8EAF0] placeholder-[#9AA1B2]/50 text-sm focus:outline-none focus:border-[#7C5CFF] focus:ring-1 focus:ring-[#7C5CFF] transition-all resize-none"
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isLoading}
              className="px-4 py-2 rounded-xl text-xs font-medium text-[#9AA1B2] hover:text-[#E8EAF0] hover:bg-[#1B1E26] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading || !name.trim()}
              className="flex items-center gap-2 px-5 py-2 rounded-xl bg-[#6C4CE8] hover:bg-[#5B3FD6] text-white text-xs font-semibold shadow-[0_0_16px_rgba(124,92,255,0.25)] transition-all disabled:opacity-50"
            >
              {isLoading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : null}
              <span>Create Project</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
