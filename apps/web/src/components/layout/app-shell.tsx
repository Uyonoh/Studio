"use client";

import { useState, type ReactNode } from "react";
import { Sidebar } from "./sidebar";
import { TopBar } from "./top-bar";
import { WorkspaceProvider, useCurrentWorkspace } from "@/components/providers/workspace-context";
import { useCreditBalance } from "@/hooks/use-credits";
import { type Workspace } from "./workspace-switcher";

interface AppShellProps {
  children: ReactNode;
  userEmail?: string | null;
  initialWorkspace?: Workspace | null;
  initialWorkspaces?: Workspace[];
}

function AppShellContent({ children, userEmail }: { children: ReactNode; userEmail?: string | null }) {
  const { workspaces, currentWorkspace, setCurrentWorkspace } = useCurrentWorkspace();
  const [isNavOpen, setIsNavOpen] = useState(false);
  const { data: creditsBalance, isLoading: isCreditsLoading } = useCreditBalance(
    currentWorkspace?.id
  );

  return (
    <div className="min-h-screen bg-[#0B0C10] text-[#E8EAF0]">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-lg focus:bg-[#6C4CE8] focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-white"
      >
        Skip to content
      </a>
      <Sidebar
        workspaces={workspaces}
        currentWorkspace={currentWorkspace}
        onSelectWorkspace={setCurrentWorkspace}
        isOpen={isNavOpen}
        onClose={() => setIsNavOpen(false)}
      />
      <div className="lg:pl-60 flex flex-col min-h-screen pt-16">
        <TopBar
          userEmail={userEmail}
          creditsBalance={creditsBalance}
          isCreditsLoading={isCreditsLoading || !currentWorkspace}
          onOpenNav={() => setIsNavOpen(true)}
        />
        <main id="main-content" tabIndex={-1} className="flex-1 p-4 sm:p-6 lg:p-8">
          {children}
        </main>
      </div>
    </div>
  );
}

export function AppShell({ initialWorkspace, initialWorkspaces, ...rest }: AppShellProps) {
  return (
    <WorkspaceProvider initialWorkspace={initialWorkspace} initialWorkspaces={initialWorkspaces}>
      <AppShellContent {...rest} />
    </WorkspaceProvider>
  );
}
