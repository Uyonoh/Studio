"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Sparkles, Image as ImageIcon, History } from "lucide-react";
import Link from "next/link";
import { getApiClient } from "@/lib/api";
import { type Project } from "@/hooks/use-projects";
import { AssetLibrary } from "@/components/assets/asset-library";

export default function ProjectWorkspacePage() {
  const params = useParams();
  const projectId = params?.id as string;
  const [project, setProject] = useState<Project | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"assets" | "composer" | "history">("assets");

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

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Back button & Project Header */}
      <div className="flex items-center gap-4">
        <Link
          href="/projects"
          className="p-2 rounded-xl bg-[#14161C] border border-[#262A35] text-[#9AA1B2] hover:text-[#E8EAF0] transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[#E8EAF0]">
            {project?.name || (isLoading ? "Loading project..." : "Project Workspace")}
          </h1>
          <p className="text-xs text-[#9AA1B2] mt-0.5">
            {project?.description || "Generative media workspace and asset pipeline."}
          </p>
        </div>
      </div>

      {/* Workspace Tabs */}
      <div className="border-b border-[#262A35] flex items-center gap-6">
        <button
          type="button"
          onClick={() => setActiveTab("assets")}
          className={`flex items-center gap-2 pb-3 border-b-2 text-sm font-semibold transition-colors ${
            activeTab === "assets"
              ? "border-[#7C5CFF] text-[#E8EAF0]"
              : "border-transparent text-[#9AA1B2] hover:text-[#E8EAF0]"
          }`}
        >
          <ImageIcon className={`w-4 h-4 ${activeTab === "assets" ? "text-[#7C5CFF]" : ""}`} />
          <span>Asset Library</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("composer")}
          className={`flex items-center gap-2 pb-3 border-b-2 text-sm font-medium transition-colors ${
            activeTab === "composer"
              ? "border-[#7C5CFF] text-[#E8EAF0]"
              : "border-transparent text-[#9AA1B2] hover:text-[#E8EAF0]"
          }`}
        >
          <Sparkles className={`w-4 h-4 ${activeTab === "composer" ? "text-[#7C5CFF]" : ""}`} />
          <span>Generation Composer</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("history")}
          className={`flex items-center gap-2 pb-3 border-b-2 text-sm font-medium transition-colors ${
            activeTab === "history"
              ? "border-[#7C5CFF] text-[#E8EAF0]"
              : "border-transparent text-[#9AA1B2] hover:text-[#E8EAF0]"
          }`}
        >
          <History className={`w-4 h-4 ${activeTab === "history" ? "text-[#7C5CFF]" : ""}`} />
          <span>Job History</span>
        </button>
      </div>

      {/* Tab Panels */}
      {activeTab === "assets" && <AssetLibrary projectId={projectId} />}

      {activeTab === "composer" && (
        <div className="rounded-2xl border border-[#262A35] bg-[#14161C] p-12 text-center">
          <p className="text-sm text-[#9AA1B2]">Generation composer will be loaded here (T6.4).</p>
        </div>
      )}

      {activeTab === "history" && (
        <div className="rounded-2xl border border-[#262A35] bg-[#14161C] p-12 text-center">
          <p className="text-sm text-[#9AA1B2]">Realtime job status & history will be loaded here (T6.5).</p>
        </div>
      )}
    </div>
  );
}
