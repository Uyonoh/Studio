"use client";

import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import { type Workspace } from "@/components/layout/workspace-switcher";
import { getApiClient } from "@/lib/api";

interface WorkspaceContextValue {
  workspaces: Workspace[];
  currentWorkspace: Workspace | null;
  setCurrentWorkspace: (ws: Workspace) => void;
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
        if (data && "workspaces" in data && Array.isArray((data as any).workspaces)) {
          const list = (data as any).workspaces;
          setWorkspaces(list);
          if (list.length > 0) {
            setCurrentWorkspace((prev) => prev || list[0]);
          }
        }
      } catch (e) {
        // Fallback for mock/test environments
      } finally {
        setIsLoading(false);
      }
    }

    loadWorkspaces();
  }, [initialWorkspace]);

  return (
    <WorkspaceContext.Provider
      value={{
        workspaces,
        currentWorkspace,
        setCurrentWorkspace,
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
