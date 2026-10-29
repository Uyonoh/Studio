"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Sparkles, Image as ImageIcon, History, Settings } from "lucide-react";
import Link from "next/link";
import { getApiClient } from "@/lib/api";
import { type Project } from "@/hooks/use-projects";

export default function ProjectWorkspacePage() {
  const params = useParams();
  const projectId = params?.id as string;
  const [project, setProject] = useState<Project | null>(null);
  const [isLoading, setIsLoading] = useState(true);

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

      {/* Workspace Tabs placeholder */}
      <div className="border-b border-[#262A35] flex items-center gap-6">
        <button
          type="button"
          className="flex items-center gap-2 pb-3 border-b-2 border-[#7C5CFF] text-[#E8EAF0] text-sm font-semibold"
        >
          <ImageIcon className="w-4 h-4 text-[#7C5CFF]" />
          <span>Asset Library</span>
        </button>
        <button
          type="button"
          className="flex items-center gap-2 pb-3 border-b-2 border-transparent text-[#9AA1B2] hover:text-[#E8EAF0] text-sm font-medium transition-colors"
        >
          <Sparkles className="w-4 h-4" />
          <span>Generation Composer</span>
        </button>
        <button
          type="button"
          className="flex items-center gap-2 pb-3 border-b-2 border-transparent text-[#9AA1B2] hover:text-[#E8EAF0] text-sm font-medium transition-colors"
        >
          <History className="w-4 h-4" />
          <span>Job History</span>
        </button>
      </div>

      <div className="rounded-2xl border border-[#262A35] bg-[#14161C] p-12 text-center">
        <p className="text-sm text-[#9AA1B2]">Project asset library and composer view.</p>
      </div>
    </div>
  );
}
