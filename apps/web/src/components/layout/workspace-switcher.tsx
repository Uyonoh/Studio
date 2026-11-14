"use client";

import { useState } from "react";
import { ChevronDown, Check, Building2 } from "lucide-react";

export interface Workspace {
  id: string;
  name: string;
  owner_id?: string;
}

interface WorkspaceSwitcherProps {
  workspaces?: Workspace[];
  currentWorkspace?: Workspace | null;
  onSelectWorkspace?: (ws: Workspace) => void;
  /** Render only the workspace icon, for a collapsed sidebar. */
  compact?: boolean;
}

export function WorkspaceSwitcher({
  workspaces = [],
  currentWorkspace,
  onSelectWorkspace,
  compact = false,
}: WorkspaceSwitcherProps) {
  const [isOpen, setIsOpen] = useState(false);

  const active = currentWorkspace || workspaces[0] || {
    id: "default",
    name: "Default Workspace",
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-label={compact ? `Switch workspace (${active.name})` : undefined}
        title={compact ? active.name : undefined}
        className={`flex items-center gap-2.5 rounded-xl hover:bg-[#1B1E26] text-left transition-colors group border border-transparent hover:border-[#262A35] focus:outline-none focus:ring-2 focus:ring-[#7C5CFF] ${
          compact ? "justify-center p-1.5" : "w-full p-2"
        }`}
      >
        <div className="w-8 h-8 rounded-lg bg-[#1B1E26] border border-[#262A35] flex items-center justify-center flex-shrink-0 text-[#A995FF]">
          <Building2 className="w-4 h-4" />
        </div>
        {!compact && (
          <>
            <div className="flex flex-col min-w-0 flex-1">
              <span className="text-sm font-semibold truncate text-[#E8EAF0] leading-tight">
                {active.name}
              </span>
              <span className="text-[11px] font-mono text-[#9AA1B2] leading-none mt-0.5">
                Studio Pro
              </span>
            </div>
            <ChevronDown className="w-4 h-4 text-[#9AA1B2] group-hover:text-[#E8EAF0] transition-colors flex-shrink-0" />
          </>
        )}
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />
          <div
            role="listbox"
            className={`absolute left-0 top-full mt-1.5 bg-[#14161C] border border-[#262A35] rounded-xl shadow-card z-50 py-1 overflow-hidden ${
              compact ? "w-56" : "w-full"
            }`}
          >
            <div className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider text-[#9AA1B2]">
              Workspaces
            </div>
            {workspaces.length === 0 ? (
              <div className="px-3 py-2 text-xs text-[#9AA1B2]">
                {active.name}
              </div>
            ) : (
              workspaces.map((ws) => (
                <button
                  key={ws.id}
                  type="button"
                  role="option"
                  aria-selected={ws.id === active.id}
                  onClick={() => {
                    onSelectWorkspace?.(ws);
                    setIsOpen(false);
                  }}
                  className="w-full flex items-center justify-between px-3 py-2 text-xs text-left text-[#E8EAF0] hover:bg-[#1B1E26] transition-colors"
                >
                  <span className="truncate">{ws.name}</span>
                  {ws.id === active.id && (
                    <Check className="w-3.5 h-3.5 text-[#A995FF] flex-shrink-0" />
                  )}
                </button>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
