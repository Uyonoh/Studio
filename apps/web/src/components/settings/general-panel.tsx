"use client";

import { useEffect, useState } from "react";
import { Check, Copy, Loader2, Save } from "lucide-react";
import { toast } from "sonner";
import { useCurrentWorkspace } from "@/components/providers/workspace-context";
import { useUpdateWorkspace } from "@/hooks/use-update-workspace";

function useCopyToClipboard() {
  const [copied, setCopied] = useState(false);

  const copy = async (value: string) => {
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(value);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1500);
      } else {
        toast.error("Clipboard access is not available in this browser.");
      }
    } catch {
      toast.error("Could not copy to the clipboard.");
    }
  };

  return { copied, copy };
}

export function GeneralPanel() {
  const { currentWorkspace, updateWorkspace } = useCurrentWorkspace();
  const [name, setName] = useState(currentWorkspace?.name ?? "");
  const [error, setError] = useState<string | null>(null);
  const updateWorkspaceMutation = useUpdateWorkspace();
  const { copied, copy } = useCopyToClipboard();

  useEffect(() => {
    setName(currentWorkspace?.name ?? "");
    setError(null);
  }, [currentWorkspace?.id, currentWorkspace?.name]);

  const trimmedName = name.trim();
  const isDirty = Boolean(currentWorkspace) && trimmedName !== currentWorkspace?.name;
  const isSaving = updateWorkspaceMutation.isPending;

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!currentWorkspace || isSaving) return;
    if (!trimmedName) {
      setError("Workspace name is required.");
      return;
    }
    if (!isDirty) return;

    setError(null);
    updateWorkspaceMutation.mutate(
      { workspaceId: currentWorkspace.id, name: trimmedName },
      {
        onSuccess: (updated) => {
          updateWorkspace({ id: updated.id, name: updated.name, owner_id: updated.owner_id });
          toast.success("Workspace name updated");
        },
        onError: (mutationError) => {
          setError(mutationError.message || "Failed to update workspace.");
        },
      }
    );
  };

  return (
    <div className="max-w-2xl space-y-6">
      <form
        onSubmit={handleSubmit}
        className="space-y-5 rounded-2xl border border-[#262A35] bg-[#14161C] p-6"
      >
        <div>
          <h3 className="text-base font-semibold text-[#E8EAF0]">Workspace details</h3>
          <p className="mt-1 text-xs text-[#9AA1B2]">
            The workspace name is shown in the sidebar switcher and across the app.
          </p>
        </div>

        <div>
          <label
            htmlFor="workspace-name"
            className="mb-1.5 block text-xs font-medium text-[#9AA1B2]"
          >
            Workspace name
          </label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              id="workspace-name"
              type="text"
              value={name}
              onChange={(event) => {
                setName(event.target.value);
                setError(null);
              }}
              maxLength={100}
              disabled={!currentWorkspace || isSaving}
              placeholder="Personal workspace"
              className="w-full rounded-xl border border-[#262A35] bg-[#0B0C10] px-4 py-2.5 text-sm text-[#E8EAF0] outline-none transition-colors focus:border-[#7C5CFF] disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={!isDirty || isSaving || !trimmedName}
              className="flex h-[42px] items-center justify-center gap-1.5 rounded-xl bg-[#6C4CE8] px-4 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {isSaving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              Save
            </button>
          </div>
          {error && <p className="mt-2 text-xs text-[#F87171]">{error}</p>}
        </div>

        <div>
          <label
            htmlFor="workspace-id"
            className="mb-1.5 block text-xs font-medium text-[#9AA1B2]"
          >
            Workspace ID
          </label>
          <div className="flex items-center gap-2">
            <input
              id="workspace-id"
              type="text"
              readOnly
              value={currentWorkspace?.id ?? "No workspace selected"}
              className="w-full rounded-xl border border-[#262A35] bg-[#0B0C10] px-4 py-2.5 font-mono text-xs text-[#9AA1B2] outline-none"
            />
            <button
              type="button"
              disabled={!currentWorkspace}
              onClick={() => currentWorkspace && copy(currentWorkspace.id)}
              aria-label="Copy workspace ID"
              className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-xl border border-[#262A35] bg-[#1B1E26] text-[#9AA1B2] transition-colors hover:text-[#E8EAF0] disabled:opacity-40"
            >
              {copied ? (
                <Check className="h-4 w-4 text-emerald-400" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>

        {currentWorkspace?.owner_id && (
          <div>
            <div className="mb-1.5 text-xs font-medium text-[#9AA1B2]">Owner ID</div>
            <div className="rounded-xl border border-[#262A35] bg-[#0B0C10] px-4 py-2.5 font-mono text-xs text-[#9AA1B2]">
              {currentWorkspace.owner_id}
            </div>
          </div>
        )}
      </form>

      <div className="rounded-2xl border border-[#262A35] bg-[#14161C] p-6">
        <h3 className="text-base font-semibold text-[#E8EAF0]">Access & roles</h3>
        <p className="mt-1 text-xs leading-relaxed text-[#9AA1B2]">
          Workspace members can be owners, admins, editors, or viewers. Only owners and admins can
          rename the workspace or manage billing. Roles are enforced by the API on every request.
        </p>
      </div>
    </div>
  );
}
