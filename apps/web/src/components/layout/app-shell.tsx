"use client";

import { type ReactNode } from "react";
import { Sidebar } from "./sidebar";
import { TopBar } from "./top-bar";
import { WorkspaceProvider, useCurrentWorkspace } from "@/components/providers/workspace-context";
import { type Workspace } from "./workspace-switcher";

interface AppShellProps {
  children: ReactNode;
  userEmail?: string | null;
  initialWorkspace?: Workspace | null;
  initialWorkspaces?: Workspace[];
}

function AppShellContent({ children, userEmail }: { children: ReactNode; userEmail?: string | null }) {
  const { workspaces, currentWorkspace, setCurrentWorkspace } = useCurrentWorkspace();

  return (
    <div className="min-h-screen bg-[#0B0C10] text-[#E8EAF0]">
      <Sidebar
        workspaces={workspaces}
        currentWorkspace={currentWorkspace}
        onSelectWorkspace={setCurrentWorkspace}
      />
      <div className="pl-60 flex flex-col min-h-screen">
        <TopBar
          userEmail={userEmail}
          creditsBalance={1000}
        />
        <main className="flex-1 pt-16 p-8">{children}</main>
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
