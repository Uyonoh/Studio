"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import {
  DEFAULT_AUTH_DESTINATION,
  safeRedirectPath,
} from "@/lib/safe-redirect";
import { Mail, Lock, ArrowRight, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";

function formatAuthError(error: string): string {
  const normalized = error.toLowerCase();

  if (error === "auth_callback_failed") {
    return "That sign-in link is invalid or has expired. Please request a new one.";
  }
  if (normalized.includes("access_denied")) {
    return "Sign in was cancelled or access was denied. Please try again.";
  }
  if (normalized.includes("provider is not enabled") || normalized.includes("not enabled")) {
    return "Google sign-in is not enabled for this project yet. Please sign in with email instead.";
  }
  return error;
}

export default function LoginPage() {
  const [authMode, setAuthMode] = useState<"magic-link" | "password">("magic-link");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const supabase = useMemo(() => createClient(), []);
  const router = useRouter();

  // Where to land after a successful sign in. Only internal paths are allowed.
  const destination = useMemo(() => {
    if (typeof window === "undefined") return DEFAULT_AUTH_DESTINATION;
    return safeRedirectPath(
      new URLSearchParams(window.location.search).get("redirectedFrom")
    );
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const err = params.get("error");
      if (err) {
        setMessage({ type: "error", text: formatAuthError(err) });
      }
    }
  }, []);

  /** Build the callback URL, preserving the post-login destination. */
  const buildCallbackUrl = () => {
    const callbackUrl = new URL("/auth/callback", window.location.origin);
    if (destination !== DEFAULT_AUTH_DESTINATION) {
      callbackUrl.searchParams.set("next", destination);
    }
    return callbackUrl.toString();
  };

  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;

    setIsLoading(true);
    setMessage(null);

    try {
      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: buildCallbackUrl(),
        },
      });

      if (error) {
        let text = error.message;
        if (text.toLowerCase().includes("rate limit")) {
          text =
            "Too many magic links requested. Wait a few minutes, or sign in with your password instead.";
        }
        setMessage({ type: "error", text });
      } else {
        setMessage({
          type: "success",
          text: `Check your inbox! We sent a magic sign-in link to ${email}. The link expires after one hour.`,
        });
      }
    } catch (err: any) {
      setMessage({ type: "error", text: err?.message || "Failed to send magic link." });
    } finally {
      setIsLoading(false);
    }
  };

  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;

    setIsLoading(true);
    setMessage(null);

    try {
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (error) {
        setMessage({ type: "error", text: error.message });
        setIsLoading(false);
      } else {
        router.push(destination);
        router.refresh();
      }
    } catch (err: any) {
      setMessage({ type: "error", text: err?.message || "Failed to sign in." });
      setIsLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setIsGoogleLoading(true);
    setMessage(null);

    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: buildCallbackUrl(),
        },
      });

      if (error) {
        setMessage({ type: "error", text: formatAuthError(error.message) });
        setIsGoogleLoading(false);
      }
    } catch (err: any) {
      setMessage({ type: "error", text: err?.message || "Failed to connect to Google." });
      setIsGoogleLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0B0C10] flex flex-col items-center justify-between p-6 relative overflow-hidden">
      {/* Subtle ambient violet radial glow */}
      <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
        <div className="w-[600px] h-[600px] rounded-full bg-[#6C4CE8] opacity-[0.08] blur-[140px] -translate-y-6"></div>
        <div className="w-[300px] h-[300px] rounded-full bg-[#6C4CE8] opacity-[0.12] blur-[80px] -translate-y-6"></div>
      </div>

      {/* Top spacer */}
      <header className="w-full max-w-[400px] flex items-center justify-end z-10 pt-2">
        <span className="text-xs text-[#9AA1B2] flex items-center gap-1.5 py-1 px-2.5 rounded-lg border border-transparent">
          AI Content Studio
        </span>
      </header>

      {/* Centered 400px Card */}
      <main className="w-full max-w-[400px] z-10 my-auto py-8">
        <div className="bg-[#14161C] border border-[#262A35] rounded-2xl p-8 shadow-card relative backdrop-blur-sm">
          {/* Logo & Brand Header */}
          <div className="flex flex-col items-center text-center mb-8">
            <div className="w-12 h-12 rounded-xl bg-[#1B1E26] border border-[#262A35] flex items-center justify-center mb-4 shadow-inner">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                <path d="M12 2L2 7L12 12L22 7L12 2Z" fill="#7C5CFF" fillOpacity="0.85" stroke="#8F75FF" strokeWidth="1.25" strokeLinejoin="round"/>
                <path d="M2 17L12 22L22 17" stroke="#7C5CFF" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M2 12L12 17L22 12" stroke="#E8EAF0" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>

            <h1 className="text-2xl font-bold tracking-tight text-[#E8EAF0] mb-1.5 flex items-center gap-2">
              <span>Studio</span>
              <span className="text-[10px] uppercase font-mono tracking-wider px-1.5 py-0.5 rounded bg-[#1B1E26] text-[#A995FF] border border-[#7C5CFF]/30">
                PRO
              </span>
            </h1>
            <p className="text-sm text-[#9AA1B2]">
              Create images and videos with AI
            </p>
          </div>

          {/* Feedback alert messages */}
          {message && (
            <div
              role="alert"
              className={`mb-5 p-3.5 rounded-xl border text-sm flex items-start gap-2.5 ${
                message.type === "success"
                  ? "bg-emerald-950/40 border-emerald-500/30 text-emerald-300"
                  : "bg-red-950/40 border-red-500/30 text-red-300"
              }`}
            >
              {message.type === "success" ? (
                <CheckCircle2 className="w-5 h-5 flex-shrink-0 text-emerald-400 mt-0.5" />
              ) : (
                <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-400 mt-0.5" />
              )}
              <span className="leading-snug">{message.text}</span>
            </div>
          )}

          {/* Actions */}
          <div className="space-y-5">
            {/* Google OAuth Button */}
            <button
              type="button"
              onClick={handleGoogleLogin}
              disabled={isGoogleLoading || isLoading}
              className="w-full flex items-center justify-center gap-3 py-2.5 px-4 rounded-xl bg-[#1B1E26] hover:bg-[#232732] border border-[#262A35] text-[#E8EAF0] font-medium text-sm transition-all hover:border-[#383E4E] focus:outline-none focus:ring-2 focus:ring-[#7C5CFF] focus:ring-offset-2 focus:ring-offset-[#14161C] disabled:opacity-50"
            >
              {isGoogleLoading ? (
                <Loader2 className="w-4 h-4 animate-spin text-[#9AA1B2]" />
              ) : (
                <svg className="w-4 h-4" viewBox="0 0 24 24" aria-hidden="true">
                  <path fill="#EA4335" d="M12 5c1.6 0 3 .6 4.1 1.6l3.1-3.1C17.3 1.7 14.8 1 12 1 7.5 1 3.7 3.6 1.9 7.3l3.7 2.9C6.5 7.2 9 5 12 5z"/>
                  <path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.7-.2-2.3H12v4.6h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5 3.7-8.9z"/>
                  <path fill="#FBBC05" d="M5.6 14.8c-.2-.7-.4-1.5-.4-2.3 0-.8.1-1.6.4-2.3L1.9 7.3C.7 9.7 0 12.3 0 15s.7 5.3 1.9 7.7l3.7-2.9z"/>
                  <path fill="#34A853" d="M12 23c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3 0-5.5-2.2-6.4-5.2L1.9 16c1.8 3.7 5.6 7 10.1 7z"/>
                </svg>
              )}
              <span>Continue with Google</span>
            </button>

            {/* Divider */}
            <div className="relative flex items-center justify-center">
              <div className="border-t border-[#262A35] w-full"></div>
              <span className="bg-[#14161C] px-3 text-xs text-[#9AA1B2] uppercase tracking-wider font-mono">
                or
              </span>
            </div>

            {/* Mode Switcher */}
            <div className="flex rounded-xl bg-[#0B0C10] p-1 border border-[#262A35]" role="tablist" aria-label="Sign in method">
              <button
                type="button"
                role="tab"
                aria-selected={authMode === "magic-link"}
                onClick={() => {
                  setAuthMode("magic-link");
                  setMessage(null);
                }}
                className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${
                  authMode === "magic-link"
                    ? "bg-[#1B1E26] text-[#E8EAF0] shadow-sm border border-[#262A35]"
                    : "text-[#9AA1B2] hover:text-[#E8EAF0]"
                }`}
              >
                Magic Link
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={authMode === "password"}
                onClick={() => {
                  setAuthMode("password");
                  setMessage(null);
                }}
                className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${
                  authMode === "password"
                    ? "bg-[#1B1E26] text-[#E8EAF0] shadow-sm border border-[#262A35]"
                    : "text-[#9AA1B2] hover:text-[#E8EAF0]"
                }`}
              >
                Password
              </button>
            </div>

            {authMode === "magic-link" ? (
              /* Email Magic Link Form */
              <form onSubmit={handleEmailLogin} className="space-y-4">
                <div className="space-y-1.5">
                  <label htmlFor="email" className="block text-xs font-medium text-[#9AA1B2]">
                    Work email
                  </label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-[#9AA1B2] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      id="email"
                      name="email"
                      type="email"
                      autoComplete="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="name@company.com"
                      className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-[#0B0C10] border border-[#262A35] text-[#E8EAF0] placeholder-[#9AA1B2]/60 text-sm focus:outline-none focus:border-[#7C5CFF] focus:ring-1 focus:ring-[#7C5CFF] transition-all"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isLoading || isGoogleLoading || !email}
                  className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-[#6C4CE8] hover:bg-[#5B3FD6] text-white font-medium text-sm transition-all shadow-[0_0_20px_rgba(124,92,255,0.25)] focus:outline-none focus:ring-2 focus:ring-[#7C5CFF] focus:ring-offset-2 focus:ring-offset-[#14161C] disabled:opacity-50 disabled:pointer-events-none"
                >
                  {isLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <span>Send Magic Link</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </form>
            ) : (
              /* Email + Password Form */
              <form onSubmit={handlePasswordLogin} className="space-y-4">
                <div className="space-y-1.5">
                  <label htmlFor="email" className="block text-xs font-medium text-[#9AA1B2]">
                    Work email
                  </label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-[#9AA1B2] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      id="email"
                      name="email"
                      type="email"
                      autoComplete="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="name@company.com"
                      className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-[#0B0C10] border border-[#262A35] text-[#E8EAF0] placeholder-[#9AA1B2]/60 text-sm focus:outline-none focus:border-[#7C5CFF] focus:ring-1 focus:ring-[#7C5CFF] transition-all"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="password" className="block text-xs font-medium text-[#9AA1B2]">
                    Password
                  </label>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-[#9AA1B2] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      id="password"
                      name="password"
                      type="password"
                      autoComplete="current-password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-[#0B0C10] border border-[#262A35] text-[#E8EAF0] placeholder-[#9AA1B2]/60 text-sm focus:outline-none focus:border-[#7C5CFF] focus:ring-1 focus:ring-[#7C5CFF] transition-all"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isLoading || isGoogleLoading || !email || !password}
                  className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-[#6C4CE8] hover:bg-[#5B3FD6] text-white font-medium text-sm transition-all shadow-[0_0_20px_rgba(124,92,255,0.25)] focus:outline-none focus:ring-2 focus:ring-[#7C5CFF] focus:ring-offset-2 focus:ring-offset-[#14161C] disabled:opacity-50 disabled:pointer-events-none"
                >
                  {isLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <span>Sign In</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </form>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="w-full max-w-[400px] text-center z-10 pb-4">
        <p className="text-xs text-[#9AA1B2]">
          By continuing, you agree to our Terms of Service and Privacy Policy.
        </p>
      </footer>
    </div>
  );
}
