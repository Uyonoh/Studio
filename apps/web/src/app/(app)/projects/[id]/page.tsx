"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Sparkles,
  Image as ImageIcon,
  History,
  LayoutGrid,
  PanelsTopLeft,
} from "lucide-react";
import Link from "next/link";
import { getApiClient } from "@/lib/api";
import { type Project } from "@/hooks/use-projects";
import { AssetLibrary } from "@/components/assets/asset-library";
import { GenerationComposer } from "@/components/composer/generation-composer";
import { JobHistory } from "@/components/jobs/job-history";
import { StudioCanvas } from "@/components/projects/studio-canvas";
import { type Asset } from "@/hooks/use-assets";

type ViewMode = "tabs" | "canvas";

const VIEW_MODE_KEY = "studio.project.view-mode";

export default function ProjectWorkspacePage() {
  const params = useParams();
  const projectId = params?.id as string;
  const [project, setProject] = useState<Project | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"assets" | "composer" | "history">(
    "assets",
  );
  const [viewMode, setViewMode] = useState<ViewMode>("tabs");
  const [seedAsset, setSeedAsset] = useState<Asset | null>(null);

  useEffect(() => {
    async function loadProject() {
      if (!projectId) return;
      try {
        const client = getApiClient();
        const res = await client.GET("/v1/projects/{project_id}", {
          params: { path: { project_id: projectId } },
        });
        if (res.data) {
          setProject(res.data as Project);
        }
      } catch (e) {
        // Fallback for mock environments
      } finally {
        setIsLoading(false);
      }
    }

    loadProject();
  }, [projectId]);

  // Restore the last-used workspace mode after mount to avoid a hydration mismatch.
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(VIEW_MODE_KEY);
      if (stored === "canvas" || stored === "tabs") setViewMode(stored);
    } catch {
      // Preference persistence is best-effort.
    }
  }, []);

  function changeViewMode(next: ViewMode) {
    setViewMode(next);
    try {
      window.localStorage.setItem(VIEW_MODE_KEY, next);
    } catch {
      // Preference persistence is best-effort.
    }
  }

  const isCanvas = viewMode === "canvas";

  return (
    <div
      className={
        isCanvas
          ? "-m-4 flex h-[calc(100vh-4rem)] flex-col overflow-hidden sm:-m-6 lg:-m-8"
          : "mx-auto max-w-7xl space-y-6"
      }
    >
      {/* Back button, project header, and view mode toggle */}
      <div
        className={
          isCanvas
            ? "flex shrink-0 items-center gap-4 border-b border-[#262A35] bg-[#0B0C10]/80 px-4 py-3 backdrop-blur-md sm:px-6 lg:px-8"
            : "flex flex-col gap-4 sm:flex-row sm:items-center"
        }
      >
        <div className="flex min-w-0 flex-1 items-center gap-4">
          <Link
            href="/projects"
            aria-label="Back to projects"
            className="shrink-0 rounded-xl border border-[#262A35] bg-[#14161C] p-2 text-[#9AA1B2] transition-colors hover:text-[#E8EAF0]"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="min-w-0">
            <h1 className="truncate text-xl font-bold tracking-tight text-[#E8EAF0]">
              {project?.name ||
                (isLoading ? "Loading project..." : "Project Workspace")}
            </h1>
            <p className="mt-0.5 truncate text-xs text-[#9AA1B2]">
              {project?.description ||
                "Generative media workspace and asset pipeline."}
            </p>
          </div>
        </div>

        <div
          role="group"
          aria-label="Project view mode"
          className="flex shrink-0 items-center self-start rounded-xl border border-[#262A35] bg-[#14161C] p-1 sm:self-auto"
        >
          <button
            type="button"
            aria-pressed={viewMode === "tabs"}
            aria-label="Tabs view"
            onClick={() => changeViewMode("tabs")}
            title="Separate tabs for assets, composer, and history"
            className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-[#7C5CFF] ${
              viewMode === "tabs"
                ? "bg-[#6C4CE8] text-white"
                : "text-[#9AA1B2] hover:text-[#E8EAF0]"
            }`}
          >
            <PanelsTopLeft className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Tabs</span>
          </button>
          <button
            type="button"
            aria-pressed={viewMode === "canvas"}
            aria-label="Canvas view"
            onClick={() => changeViewMode("canvas")}
            title="Canvas view with an infinite prompt dock"
            className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-[#7C5CFF] ${
              viewMode === "canvas"
                ? "bg-[#6C4CE8] text-white"
                : "text-[#9AA1B2] hover:text-[#E8EAF0]"
            }`}
          >
            <LayoutGrid className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Canvas</span>
          </button>
        </div>
      </div>

      {isCanvas ? (
        <StudioCanvas projectId={projectId} />
      ) : (
        <>
          {/* Workspace Tabs */}
          <div
            role="tablist"
            aria-label="Project workspace sections"
            className="flex items-center gap-4 overflow-x-auto border-b border-[#262A35] sm:gap-6"
          >
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "assets"}
              onClick={() => setActiveTab("assets")}
              className={`flex shrink-0 items-center gap-2 whitespace-nowrap border-b-2 pb-3 text-sm font-semibold transition-colors ${
                activeTab === "assets"
                  ? "border-[#7C5CFF] text-[#E8EAF0]"
                  : "border-transparent text-[#9AA1B2] hover:text-[#E8EAF0]"
              }`}
            >
              <ImageIcon
                className={`h-4 w-4 ${activeTab === "assets" ? "text-[#A995FF]" : ""}`}
              />
              <span>Asset Library</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "composer"}
              onClick={() => setActiveTab("composer")}
              className={`flex shrink-0 items-center gap-2 whitespace-nowrap border-b-2 pb-3 text-sm font-medium transition-colors ${
                activeTab === "composer"
                  ? "border-[#7C5CFF] text-[#E8EAF0]"
                  : "border-transparent text-[#9AA1B2] hover:text-[#E8EAF0]"
              }`}
            >
              <Sparkles
                className={`h-4 w-4 ${activeTab === "composer" ? "text-[#A995FF]" : ""}`}
              />
              <span>Generation Composer</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "history"}
              onClick={() => setActiveTab("history")}
              className={`flex shrink-0 items-center gap-2 whitespace-nowrap border-b-2 pb-3 text-sm font-medium transition-colors ${
                activeTab === "history"
                  ? "border-[#7C5CFF] text-[#E8EAF0]"
                  : "border-transparent text-[#9AA1B2] hover:text-[#E8EAF0]"
              }`}
            >
              <History
                className={`h-4 w-4 ${activeTab === "history" ? "text-[#A995FF]" : ""}`}
              />
              <span>Job History</span>
            </button>
          </div>

          {/* Tab Panels */}
          <div role="tabpanel" aria-label="Project workspace content">
            {activeTab === "assets" && <AssetLibrary projectId={projectId} />}

            {activeTab === "composer" && (
              <GenerationComposer
                key={seedAsset?.id ?? "composer"}
                projectId={projectId}
                initialAsset={seedAsset}
              />
            )}

            {activeTab === "history" && (
              <JobHistory
                projectId={projectId}
                onUseAsInput={(asset) => {
                  setSeedAsset(asset);
                  setActiveTab("composer");
                }}
              />
            )}
          </div>
        </>
      )}
    </div>
  );
}
