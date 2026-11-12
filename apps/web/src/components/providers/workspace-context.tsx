"use client";

import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import { type Workspace } from "@/components/layout/workspace-switcher";
import { getApiClient } from "@/lib/api";

interface WorkspaceContextValue {
  workspaces: Workspace[];
  currentWorkspace: Workspace | null;
  setCurrentWorkspace: (ws: Workspace) => void;
  updateWorkspace: (ws: Workspace) => void;
  isLoading: boolean;
}

const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(undefined);

interface WorkspaceProviderProps {
  children: ReactNode;
  initialWorkspace?: Workspace | null;
  initialWorkspaces?: Workspace[];
}

export function WorkspaceProvider({
  children,
  initialWorkspace,
  initialWorkspaces,
}: WorkspaceProviderProps) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>(
    initialWorkspaces || (initialWorkspace ? [initialWorkspace] : [])
  );
  const [currentWorkspace, setCurrentWorkspace] = useState<Workspace | null>(
    initialWorkspace || null
  );
  const [isLoading, setIsLoading] = useState(!initialWorkspace);

  useEffect(() => {
    if (initialWorkspace) return;

    async function loadWorkspaces() {
      try {
        const client = getApiClient();
        const { data } = await client.GET("/v1/workspaces");
        let list: Workspace[] = [];
        if (Array.isArray(data)) {
          list = data as Workspace[];
        } else if (data && "workspaces" in data && Array.isArray((data as any).workspaces)) {
          list = (data as any).workspaces;
        }
        if (list.length > 0) {
          setWorkspaces(list);
          const savedId = typeof window !== "undefined" ? localStorage.getItem("studio_active_workspace_id") : null;
          const matched = savedId ? list.find((w) => w.id === savedId) : null;
          setCurrentWorkspace(matched || list[0]);
        }
      } catch (e) {
        // Fallback for mock/test environments
      } finally {
        setIsLoading(false);
      }
    }

    loadWorkspaces();
  }, [initialWorkspace]);

  const handleSelectWorkspace = (ws: Workspace) => {
    setCurrentWorkspace(ws);
    if (typeof window !== "undefined") {
      localStorage.setItem("studio_active_workspace_id", ws.id);
    }
  };

  const handleUpdateWorkspace = (ws: Workspace) => {
    setWorkspaces((prev) => prev.map((item) => (item.id === ws.id ? { ...item, ...ws } : item)));
    setCurrentWorkspace((prev) => (prev && prev.id === ws.id ? { ...prev, ...ws } : prev));
  };

  return (
    <WorkspaceContext.Provider
      value={{
        workspaces,
        currentWorkspace,
        setCurrentWorkspace: handleSelectWorkspace,
        updateWorkspace: handleUpdateWorkspace,
        isLoading,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useCurrentWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error("useCurrentWorkspace must be used within a WorkspaceProvider");
  }
  return context;
}
