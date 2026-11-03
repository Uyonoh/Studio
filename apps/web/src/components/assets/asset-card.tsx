"use client";

import { useState, useRef } from "react";
import { type Asset } from "@/hooks/use-assets";
import { Image as ImageIcon, Video, Film, Eye } from "lucide-react";

interface AssetCardProps {
  asset: Asset;
  onClick: (asset: Asset) => void;
  /** Called when the signed media URL fails to load (e.g. it expired). */
  onMediaError?: (asset: Asset) => void;
}

export function AssetCard({ asset, onClick, onMediaError }: AssetCardProps) {
  const [isHovered, setIsHovered] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const mediaErrorReported = useRef(false);

  const isVideo = asset.kind === "video" || asset.mime_type?.startsWith("video/");
  const displaySrc = asset.signed_url || asset.thumbnail_url || "";

  const handleMediaError = () => {
    if (mediaErrorReported.current) return;
    mediaErrorReported.current = true;
    onMediaError?.(asset);
  };

  const handleMouseEnter = () => {
    setIsHovered(true);
    if (isVideo && videoRef.current) {
      videoRef.current.play().catch(() => {
        // Autoplay may fail if muted/user policy, safe to ignore
      });
    }
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
    if (isVideo && videoRef.current) {
      videoRef.current.pause();
      videoRef.current.currentTime = 0;
    }
  };

  return (
    <div
      onClick={() => onClick(asset)}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick(asset);
        }
      }}
      className="group relative bg-[#14161C] border border-[#262A35] hover:border-[#7C5CFF]/60 rounded-2xl overflow-hidden cursor-pointer transition-all hover:shadow-[0_4px_24px_rgba(124,92,255,0.15)] flex flex-col focus:outline-none focus:ring-2 focus:ring-[#7C5CFF]"
    >
      {/* Media Preview Container */}
      <div className="relative aspect-square w-full bg-[#0E1015] overflow-hidden flex items-center justify-center">
        {isVideo ? (
          <>
            {/* If video has a signed url, play on hover */}
            {asset.signed_url ? (
              <video
                ref={videoRef}
                src={asset.signed_url}
                muted
                loop
                playsInline
                preload="metadata"
                onError={handleMediaError}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
              />
            ) : asset.thumbnail_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={asset.thumbnail_url}
                alt="Video thumbnail"
                onError={handleMediaError}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
              />
            ) : (
              <div className="flex flex-col items-center justify-center gap-2 text-[#9AA1B2]">
                <Film className="w-8 h-8 text-[#A995FF]" />
                <span className="text-[10px] font-mono">Video</span>
              </div>
            )}
            <div className="absolute top-2.5 right-2.5 px-2 py-0.5 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center gap-1.5 text-[10px] font-medium text-white z-10">
              <Video className="w-3 h-3 text-[#A995FF]" />
              <span>{asset.duration_ms ? `${(asset.duration_ms / 1000).toFixed(1)}s` : "Video"}</span>
            </div>
          </>
        ) : displaySrc ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={displaySrc}
            alt={asset.metadata?.filename || "Asset image"}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
            onError={handleMediaError}
          />
        ) : (
          <div className="flex flex-col items-center justify-center gap-2 text-[#9AA1B2]">
            <ImageIcon className="w-8 h-8 text-[#A995FF]" />
            <span className="text-[10px] font-mono">Image</span>
          </div>
        )}

        {/* Hover overlay hint */}
        <div
          className={`absolute inset-0 bg-black/40 backdrop-blur-[2px] flex items-center justify-center transition-opacity ${
            isHovered ? "opacity-100" : "opacity-0"
          }`}
        >
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#14161C]/90 border border-white/10 text-xs font-medium text-[#E8EAF0] shadow-lg">
            <Eye className="w-3.5 h-3.5 text-[#A995FF]" />
            <span>View Details</span>
          </div>
        </div>

        {/* Origin Badge */}
        <div className="absolute top-2.5 left-2.5 px-2 py-0.5 rounded-full bg-black/60 backdrop-blur-md border border-white/10 text-[10px] font-mono capitalize text-[#9AA1B2]">
          {asset.origin}
        </div>
      </div>

      {/* Info bar */}
      <div className="p-3 bg-[#14161C] flex items-center justify-between text-xs border-t border-[#262A35]">
        <div className="truncate max-w-[140px] text-[#E8EAF0] font-medium">
          {asset.metadata?.filename || `${asset.kind}-${asset.id.slice(0, 8)}`}
        </div>
        <div className="text-[11px] font-mono text-[#9AA1B2]">
          {asset.width && asset.height
            ? `${asset.width}x${asset.height}`
            : asset.size_bytes
            ? `${(asset.size_bytes / (1024 * 1024)).toFixed(1)} MB`
            : ""}
        </div>
      </div>
    </div>
  );
}
