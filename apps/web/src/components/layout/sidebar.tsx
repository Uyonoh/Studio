"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FolderOpen, Images, Sparkles, Settings, Activity } from "lucide-react";
import { WorkspaceSwitcher, type Workspace } from "./workspace-switcher";

interface SidebarProps {
  workspaces?: Workspace[];
  currentWorkspace?: Workspace | null;
  onSelectWorkspace?: (ws: Workspace) => void;
}

export function Sidebar({
  workspaces,
  currentWorkspace,
  onSelectWorkspace,
}: SidebarProps) {
  const pathname = usePathname();

  const navItems = [
    { label: "Projects", href: "/projects", icon: FolderOpen },
    { label: "Assets", href: "/assets", icon: Images },
    { label: "Generations", href: "/generations", icon: Sparkles },
    { label: "Settings", href: "/settings", icon: Settings },
  ];

  return (
    <aside
      aria-label="Main Navigation"
      className="fixed left-0 top-0 h-full w-60 bg-[#121317] border-r border-[#262A35] z-30 flex flex-col justify-between select-none"
    >
      <div className="flex flex-col">
        {/* Workspace Switcher Header */}
        <div className="h-16 px-3 border-b border-[#262A35] flex items-center">
          <WorkspaceSwitcher
            workspaces={workspaces}
            currentWorkspace={currentWorkspace}
            onSelectWorkspace={onSelectWorkspace}
          />
        </div>

        {/* Navigation */}
        <div className="px-4 pt-5 pb-2">
          <span className="text-[10px] font-mono uppercase tracking-wider text-[#9AA1B2] px-2">
            Workspace
          </span>
        </div>

        <nav className="flex flex-col gap-1 px-3">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              pathname === item.href ||
              (item.href !== "/" && pathname?.startsWith(item.href));

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors group ${
                  isActive
                    ? "bg-[#1B1E26] text-[#E8EAF0] border border-[#262A35]"
                    : "text-[#9AA1B2] hover:bg-[#1B1E26]/50 hover:text-[#E8EAF0]"
                }`}
              >
                <Icon
                  className={`w-4 h-4 transition-colors ${
                    isActive
                      ? "text-[#7C5CFF]"
                      : "text-[#9AA1B2] group-hover:text-[#E8EAF0]"
                  }`}
                />
                <span className="flex-1">{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Footer Info */}
      <div className="p-4 border-t border-[#262A35] flex flex-col gap-3">
        <div className="flex items-center justify-between text-xs text-[#9AA1B2]">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span className="font-mono text-[11px]">System Online</span>
          </div>
          <Activity className="w-3.5 h-3.5 text-[#9AA1B2]" />
        </div>
      </div>
    </aside>
  );
}
