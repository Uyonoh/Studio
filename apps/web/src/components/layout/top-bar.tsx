"use client";

import { useState } from "react";
import { Zap, LogOut, User, ChevronDown } from "lucide-react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

interface TopBarProps {
  userEmail?: string | null;
  creditsBalance?: number;
  title?: string;
}

export function TopBar({
  userEmail,
  creditsBalance = 1000,
  title = "Projects",
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
    <header className="fixed top-0 left-60 right-0 h-16 bg-[#0B0C10]/80 backdrop-blur-xl border-b border-[#262A35] z-20 flex items-center justify-between px-6 select-none">
      {/* Title / Breadcrumb */}
      <div className="flex items-center gap-2 text-sm">
        <span className="text-[#9AA1B2]">Studio</span>
        <span className="text-[#9AA1B2]/50">/</span>
        <span className="font-semibold text-[#E8EAF0]">{title}</span>
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-4">
        {/* Credits Badge */}
        <div
          data-testid="credits-balance"
          className="flex items-center gap-2 h-9 px-3.5 rounded-xl bg-[#14161C] border border-[#262A35] text-xs font-mono text-[#E8EAF0]"
        >
          <Zap className="w-3.5 h-3.5 text-[#7C5CFF] fill-[#7C5CFF]/20" />
          <span className="font-semibold">{creditsBalance.toLocaleString()}</span>
          <span className="text-[#9AA1B2] font-sans">Credits</span>
        </div>

        {/* User Menu */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            aria-expanded={isMenuOpen}
            aria-label="User menu"
            className="flex items-center gap-2 p-1.5 rounded-xl hover:bg-[#14161C] border border-transparent hover:border-[#262A35] transition-all"
          >
            <div className="w-8 h-8 rounded-full bg-[#1B1E26] border border-[#7C5CFF]/40 text-[#7C5CFF] flex items-center justify-center font-semibold text-xs">
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
