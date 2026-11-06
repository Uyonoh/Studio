"use client";

import { useState } from "react";
import { useCurrentWorkspace } from "@/components/providers/workspace-context";
import { useProjects } from "@/hooks/use-projects";
import { AssetLibrary } from "@/components/assets/asset-library";
import { Folder, FolderOpen, Images, AlertCircle, Plus, Search } from "lucide-react";
import Link from "next/link";

export default function AssetsGlobalPage() {
  const { currentWorkspace, isLoading: isLoadingWorkspace } = useCurrentWorkspace();
  const workspaceId = currentWorkspace?.id;
  const { data: projectsData, isLoading: isLoadingProjects } = useProjects(workspaceId);
  const projects = (projectsData?.items || []).filter((p) => !p.archived_at);

  const [selectedProjectId, setSelectedProjectId] = useState<string>("");

  const activeProjectId = selectedProjectId || (projects.length > 0 ? projects[0].id : "");
  const activeProject = projects.find((p) => p.id === activeProjectId);

  const isLoading = isLoadingWorkspace || isLoadingProjects;

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-[#E8EAF0]">
              Asset Library
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-mono bg-[#1B1E26] text-[#A995FF] border border-[#262A35]">
              {projects.length} {projects.length === 1 ? "project" : "projects"}
            </span>
          </div>
          <p className="text-sm text-[#9AA1B2] mt-1">
            Browse, manage, and upload media assets across your workspace.
          </p>
        </div>

        {/* Project Selector pill */}
        {projects.length > 0 && (
          <div className="flex items-center gap-2">
            <label htmlFor="project-picker" className="text-xs text-[#9AA1B2] font-medium">
              Project:
            </label>
            <div className="relative">
              <select
                id="project-picker"
                value={activeProjectId}
                onChange={(e) => setSelectedProjectId(e.target.value)}
                className="appearance-none bg-[#14161C] border border-[#262A35] text-[#E8EAF0] text-sm rounded-xl px-3 py-2 pr-8 focus:outline-none focus:border-[#7C5CFF] transition-colors"
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <FolderOpen className="w-4 h-4 text-[#9AA1B2] absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="p-12 rounded-2xl bg-[#14161C] border border-[#262A35] flex flex-col items-center justify-center text-center">
          <div className="w-8 h-8 rounded-full border-2 border-[#7C5CFF] border-t-transparent animate-spin mb-4" />
          <p className="text-sm text-[#9AA1B2]">Loading workspace assets...</p>
        </div>
      ) : projects.length === 0 ? (
        <div className="p-12 rounded-2xl bg-[#14161C] border border-[#262A35] flex flex-col items-center justify-center text-center max-w-md mx-auto">
          <div className="w-12 h-12 rounded-xl bg-[#1B1E26] border border-[#262A35] flex items-center justify-center text-[#A995FF] mb-4">
            <Images className="w-6 h-6" />
          </div>
          <h3 className="text-base font-semibold text-[#E8EAF0] mb-1">
            No projects found
          </h3>
          <p className="text-sm text-[#9AA1B2] mb-6">
            Assets belong to projects. Create your first project to upload images or videos and start generating.
          </p>
          <Link
            href="/projects"
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#6C4CE8] hover:bg-[#5B3FD6] text-white text-sm font-medium transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>Create a Project</span>
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-[#9AA1B2] border-b border-[#262A35] pb-3">
            <span className="font-medium">
              Showing assets for:{" "}
              <strong className="text-[#E8EAF0]">{activeProject?.name}</strong>
            </span>
            <Link
              href={`/projects/${activeProjectId}`}
              className="text-[#A995FF] hover:underline flex items-center gap-1"
            >
              Open project workspace →
            </Link>
          </div>

          <AssetLibrary projectId={activeProjectId} />
        </div>
      )}
    </div>
  );
}
