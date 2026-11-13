"use client";

import { useState } from "react";
import Link from "next/link";
import { Folder, MoreVertical, Edit2, Archive, Calendar, Sparkles, Video } from "lucide-react";
import { type Project, type ProjectPreviewAsset } from "@/hooks/use-projects";

interface ProjectCardProps {
  project: Project;
  onRename: (project: Project) => void;
  onArchive: (project: Project) => void;
}

function previewSource(preview: ProjectPreviewAsset): string | null {
  if (preview.thumbnail_url) return preview.thumbnail_url;
  // Video originals cannot be rendered as an <img>; only images fall back.
  if (preview.kind === "image") return preview.signed_url;
  return null;
}

function ProjectPreviewMosaic({ project }: { project: Project }) {
  const [failedAssetIds, setFailedAssetIds] = useState<Set<string>>(() => new Set());
  const previews = (project.previews ?? [])
    .filter((preview) => previewSource(preview) && !failedAssetIds.has(preview.asset_id))
    .slice(0, 4);

  if (previews.length === 0) {
    return (
      <div className="absolute inset-0 flex items-center justify-center text-[#A995FF]/30 group-hover:text-[#A995FF]/50 transition-colors">
        <Folder className="w-12 h-12" />
      </div>
    );
  }

  const count = previews.length;
  const gridClass =
    count === 1
      ? "grid-cols-1 grid-rows-1"
      : count === 2
        ? "grid-cols-2 grid-rows-1"
        : "grid-cols-2 grid-rows-2";

  return (
    <div className={`grid h-full w-full gap-0.5 ${gridClass}`}>
      {previews.map((preview, index) => {
        const src = previewSource(preview);
        if (!src) return null;
        const isVideo = preview.kind === "video";

        return (
          <div
            key={preview.asset_id}
            className={`relative min-h-0 min-w-0 overflow-hidden bg-[#0E1015] ${
              count === 3 && index === 0 ? "row-span-2" : ""
            }`}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={src}
              alt={index === 0 ? `Preview of ${project.name}` : ""}
              aria-hidden={index === 0 ? undefined : true}
              loading="lazy"
              className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
              onError={() =>
                setFailedAssetIds((current) => {
                  const next = new Set(current);
                  next.add(preview.asset_id);
                  return next;
                })
              }
            />
            {(isVideo || preview.origin === "generated") && (
              <span className="absolute bottom-1 right-1 flex items-center gap-1 rounded-full bg-black/60 px-1.5 py-0.5 text-[9px] font-medium text-white backdrop-blur-md">
                {isVideo ? (
                  <Video className="h-2.5 w-2.5 text-[#A995FF]" aria-hidden="true" />
                ) : (
                  <Sparkles className="h-2.5 w-2.5 text-[#A995FF]" aria-hidden="true" />
                )}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function ProjectCard({ project, onRename, onArchive }: ProjectCardProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const formattedDate = new Date(project.updated_at || project.created_at).toLocaleDateString(
    undefined,
    { month: "short", day: "numeric" }
  );

  return (
    <div className="group relative bg-[#14161C] border border-[#262A35] hover:border-[#383E4E] rounded-2xl overflow-hidden shadow-card transition-all flex flex-col justify-between">
      {/* Cover / Preview Area */}
      <Link
        href={`/projects/${project.id}`}
        aria-label={`Open ${project.name}`}
        className="block aspect-[16/9] bg-[#0E1015] relative overflow-hidden group-hover:opacity-95 transition-opacity"
      >
        <ProjectPreviewMosaic project={project} />
        <div className="absolute inset-0 bg-gradient-to-t from-[#14161C] via-transparent to-transparent z-10 pointer-events-none" />
      </Link>

      {/* Content */}
      <div className="p-4 flex flex-col justify-between flex-1">
        <div>
          <div className="flex items-start justify-between gap-2">
            <Link
              href={`/projects/${project.id}`}
              className="text-sm font-semibold text-[#E8EAF0] hover:text-[#A995FF] transition-colors line-clamp-1"
            >
              {project.name}
            </Link>

            {/* Menu */}
            <div className="relative">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setIsMenuOpen(!isMenuOpen);
                }}
                aria-label={`Options for ${project.name}`}
                aria-expanded={isMenuOpen}
                className="p-1 rounded-lg text-[#9AA1B2] hover:text-[#E8EAF0] hover:bg-[#1B1E26] transition-colors"
              >
                <MoreVertical className="w-4 h-4" />
              </button>

              {isMenuOpen && (
                <>
                  <div
                    className="fixed inset-0 z-20"
                    onClick={() => setIsMenuOpen(false)}
                  />
                  <div
                    role="menu"
                    className="absolute right-0 top-full mt-1 w-36 bg-[#14161C] border border-[#262A35] rounded-xl shadow-card z-30 py-1 overflow-hidden"
                  >
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setIsMenuOpen(false);
                        onRename(project);
                      }}
                      className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-[#E8EAF0] hover:bg-[#1B1E26] transition-colors text-left"
                    >
                      <Edit2 className="w-3.5 h-3.5 text-[#9AA1B2]" />
                      <span>Rename</span>
                    </button>
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setIsMenuOpen(false);
                        onArchive(project);
                      }}
                      className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10 transition-colors text-left"
                    >
                      <Archive className="w-3.5 h-3.5" />
                      <span>Archive</span>
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>

          <p className="text-xs text-[#9AA1B2] mt-1 line-clamp-2 min-h-[2rem]">
            {project.description || "No description provided."}
          </p>
        </div>

        <div className="flex items-center justify-between pt-3 mt-2 border-t border-[#262A35]/60 text-[11px] font-mono text-[#9AA1B2]">
          <span className="flex items-center gap-1.5">
            <Calendar className="w-3 h-3 text-[#9AA1B2]/60" />
            <span>Updated {formattedDate}</span>
          </span>
          <span className="text-[10px] uppercase font-semibold text-[#A995FF] tracking-wider px-1.5 py-0.5 rounded bg-[#1B1E26]">
            Active
          </span>
        </div>
      </div>
    </div>
  );
}
