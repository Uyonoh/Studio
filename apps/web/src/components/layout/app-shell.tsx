"use client";

import { useState, useEffect, type ReactNode } from "react";
import { Sidebar } from "./sidebar";
import { TopBar } from "./top-bar";
import { type Workspace } from "./workspace-switcher";
import { getApiClient } from "@/lib/api";

interface AppShellProps {
  children: ReactNode;
  userEmail?: string | null;
}

export function AppShell({ children, userEmail }: AppShellProps) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [currentWorkspace, setCurrentWorkspace] = useState<Workspace | null>(null);
  const [creditsBalance, setCreditsBalance] = useState<number>(1000);

  useEffect(() => {
    async function loadWorkspaces() {
      try {
        const client = getApiClient();
        const { data } = await client.GET("/v1/workspaces");
        if (data && "workspaces" in data && Array.isArray((data as any).workspaces)) {
          const list = (data as any).workspaces;
          setWorkspaces(list);
          if (list.length > 0) {
            setCurrentWorkspace((prev) => prev || list[0]);
          }
        }
      } catch (e) {
        // Fallback for offline or local dev without API running
      }
    }

    loadWorkspaces();
  }, []);

  return (
    <div className="min-h-screen bg-[#0B0C10] text-[#E8EAF0]">
      <Sidebar
        workspaces={workspaces}
        currentWorkspace={currentWorkspace}
        onSelectWorkspace={(ws) => setCurrentWorkspace(ws)}
      />
      <div className="pl-60 flex flex-col min-h-screen">
        <TopBar
          userEmail={userEmail}
          creditsBalance={creditsBalance}
        />
        <main className="flex-1 pt-16 p-8">{children}</main>
      </div>
    </div>
  );
}
