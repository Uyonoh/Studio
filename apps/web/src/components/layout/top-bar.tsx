"use client";

import { useState } from "react";
import Link from "next/link";
import { Zap, LogOut, ChevronDown, Menu, Settings } from "lucide-react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

interface TopBarProps {
  userEmail?: string | null;
  creditsBalance?: number;
  isCreditsLoading?: boolean;
  title?: string;
  /** Opens the off-canvas navigation on small screens. */
  onOpenNav?: () => void;
}

export function TopBar({
  userEmail,
  creditsBalance,
  isCreditsLoading = false,
  title = "Projects",
  onOpenNav,
}: TopBarProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const router = useRouter();
  const supabase = createClient();

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    router.push("/login");
  };

  const initial = userEmail ? userEmail[0].toUpperCase() : "U";

  return (
    <header className="fixed top-0 left-0 lg:left-60 right-0 h-16 bg-[#0B0C10]/80 backdrop-blur-xl border-b border-[#262A35] z-20 flex items-center justify-between gap-3 px-3 sm:px-6 select-none">
      {/* Title / Breadcrumb */}
      <div className="flex items-center gap-2 text-sm min-w-0">
        <button
          type="button"
          onClick={onOpenNav}
          aria-label="Open navigation"
          aria-controls="main-navigation"
          className="lg:hidden p-1.5 -ml-1 rounded-lg text-[#9AA1B2] hover:text-[#E8EAF0] hover:bg-[#14161C] transition-colors shrink-0"
        >
          <Menu className="w-5 h-5" />
        </button>
        <span className="hidden sm:inline text-[#9AA1B2]">Studio</span>
        <span className="hidden sm:inline text-[#9AA1B2]/50">/</span>
        <span className="font-semibold text-[#E8EAF0] truncate">{title}</span>
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-2 sm:gap-4 shrink-0">
        {/* Credits Badge — links to the usage section of settings */}
        <Link
          href="/settings?tab=usage"
          data-testid="credits-balance"
          title="View credit usage in the active workspace"
          aria-label={
            isCreditsLoading || creditsBalance === undefined
              ? "View credit usage"
              : `View credit usage. ${creditsBalance.toLocaleString(undefined, {
                  maximumFractionDigits: 2,
                })} credits available`
          }
          aria-busy={isCreditsLoading}
          className="flex h-9 items-center gap-1.5 rounded-xl border border-[#262A35] bg-[#14161C] px-2.5 text-xs font-mono text-[#E8EAF0] transition-colors hover:border-[#7C5CFF]/50 hover:bg-[#1B1E26] sm:gap-2 sm:px-3.5"
        >
          <Zap className="w-3.5 h-3.5 text-[#A995FF] fill-[#7C5CFF]/20" />
          <span className={`font-semibold ${isCreditsLoading ? "animate-pulse text-[#9AA1B2]" : ""}`}>
            {isCreditsLoading || creditsBalance === undefined
              ? "—"
              : creditsBalance.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </span>
          <span className="hidden sm:inline text-[#9AA1B2] font-sans">Credits</span>
        </Link>

        {/* User Menu */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            aria-expanded={isMenuOpen}
            aria-label="User menu"
            className="flex items-center gap-2 p-1.5 rounded-xl hover:bg-[#14161C] border border-transparent hover:border-[#262A35] transition-all"
          >
            <div className="w-8 h-8 rounded-full bg-[#1B1E26] border border-[#7C5CFF]/40 text-[#A995FF] flex items-center justify-center font-semibold text-xs">
              {initial}
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-[#9AA1B2]" />
          </button>

          {isMenuOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setIsMenuOpen(false)}
              />
              <div
                role="menu"
                className="absolute right-0 top-full mt-2 w-56 bg-[#14161C] border border-[#262A35] rounded-xl shadow-card z-50 py-1.5 overflow-hidden"
              >
                <div className="px-3.5 py-2 border-b border-[#262A35]">
                  <div className="text-[10px] font-mono text-[#9AA1B2] uppercase">
                    Signed in as
                  </div>
                  <div className="text-xs font-medium text-[#E8EAF0] truncate mt-0.5">
                    {userEmail || "user@example.com"}
                  </div>
                </div>

                <div className="p-1">
                  <Link
                    href="/settings?tab=usage"
                    onClick={() => setIsMenuOpen(false)}
                    className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs text-[#E8EAF0] transition-colors hover:bg-[#1B1E26]"
                  >
                    <Zap className="w-4 h-4 text-[#A995FF]" />
                    <span>Usage &amp; billing</span>
                  </Link>
                  <Link
                    href="/settings"
                    onClick={() => setIsMenuOpen(false)}
                    className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs text-[#E8EAF0] transition-colors hover:bg-[#1B1E26]"
                  >
                    <Settings className="w-4 h-4 text-[#9AA1B2]" />
                    <span>Workspace settings</span>
                  </Link>
                  <button
                    type="button"
                    onClick={handleSignOut}
                    className="w-full flex items-center gap-2.5 px-3 py-2 text-xs rounded-lg text-red-400 hover:bg-red-500/10 transition-colors"
                  >
                    <LogOut className="w-4 h-4" />
                    <span>Sign Out</span>
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
