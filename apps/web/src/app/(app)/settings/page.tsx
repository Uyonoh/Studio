"use client";

import { useState } from "react";
import { useCurrentWorkspace } from "@/components/providers/workspace-context";
import {
  Building2,
  Zap,
  CreditCard,
  Shield,
  Key,
  Database,
  CheckCircle2,
  Cpu,
  Layers,
  Sparkles,
  ExternalLink,
} from "lucide-react";

export default function SettingsPage() {
  const { currentWorkspace } = useCurrentWorkspace();
  const [activeTab, setActiveTab] = useState<"general" | "billing" | "api" | "models">("billing");

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-[#E8EAF0]">
              Workspace & Settings
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-mono bg-[#1B1E26] text-[#A995FF] border border-[#262A35]">
              {currentWorkspace?.name || "Active Workspace"}
            </span>
          </div>
          <p className="text-sm text-[#9AA1B2] mt-1">
            Manage your workspace preferences, model configurations, API credentials, and credits.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div
        role="tablist"
        aria-label="Settings sections"
        className="border-b border-[#262A35] flex items-center gap-6"
      >
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "billing"}
          onClick={() => setActiveTab("billing")}
          className={`flex items-center gap-2 pb-3 border-b-2 text-sm font-medium transition-colors ${
            activeTab === "billing"
              ? "border-[#7C5CFF] text-[#E8EAF0] font-semibold"
              : "border-transparent text-[#9AA1B2] hover:text-[#E8EAF0]"
          }`}
        >
          <CreditCard className="w-4 h-4" />
          <span>Usage & Billing</span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "general"}
          onClick={() => setActiveTab("general")}
          className={`flex items-center gap-2 pb-3 border-b-2 text-sm font-medium transition-colors ${
            activeTab === "general"
              ? "border-[#7C5CFF] text-[#E8EAF0] font-semibold"
              : "border-transparent text-[#9AA1B2] hover:text-[#E8EAF0]"
          }`}
        >
          <Building2 className="w-4 h-4" />
          <span>General</span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "models"}
          onClick={() => setActiveTab("models")}
          className={`flex items-center gap-2 pb-3 border-b-2 text-sm font-medium transition-colors ${
            activeTab === "models"
              ? "border-[#7C5CFF] text-[#E8EAF0] font-semibold"
              : "border-transparent text-[#9AA1B2] hover:text-[#E8EAF0]"
          }`}
        >
          <Cpu className="w-4 h-4" />
          <span>AI Models & Providers</span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "api"}
          onClick={() => setActiveTab("api")}
          className={`flex items-center gap-2 pb-3 border-b-2 text-sm font-medium transition-colors ${
            activeTab === "api"
              ? "border-[#7C5CFF] text-[#E8EAF0] font-semibold"
              : "border-transparent text-[#9AA1B2] hover:text-[#E8EAF0]"
          }`}
        >
          <Key className="w-4 h-4" />
          <span>API & Webhooks</span>
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === "billing" && (
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Credits Card */}
            <div className="p-6 rounded-2xl bg-[#14161C] border border-[#262A35] relative overflow-hidden group">
              <div className="absolute -right-6 -top-6 w-32 h-32 rounded-full bg-[#7C5CFF]/10 blur-2xl pointer-events-none" />
              <div className="flex items-center justify-between text-xs text-[#9AA1B2] mb-3">
                <span className="font-mono uppercase tracking-wider">Available Balance</span>
                <span className="px-2 py-0.5 rounded-full bg-[#1B1E26] text-[#A995FF] border border-[#262A35] flex items-center gap-1">
                  <Zap className="w-3 h-3" />
                  Active
                </span>
              </div>
              <div className="flex items-baseline gap-2 mb-2">
                <span className="text-3xl font-bold text-[#E8EAF0] tracking-tight">1,000</span>
                <span className="text-sm text-[#9AA1B2]">credits</span>
              </div>
              <p className="text-xs text-[#9AA1B2] leading-relaxed">
                Credits are deducted per model generation and refunded automatically if a provider job fails or is canceled.
              </p>
            </div>

            {/* Plan Tier */}
            <div className="p-6 rounded-2xl bg-[#14161C] border border-[#262A35]">
              <div className="flex items-center justify-between text-xs text-[#9AA1B2] mb-3">
                <span className="font-mono uppercase tracking-wider">Current Plan</span>
                <span className="px-2 py-0.5 rounded-full bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30">
                  Pro Tier
                </span>
              </div>
              <div className="text-xl font-bold text-[#E8EAF0] mb-2">Studio Professional</div>
              <p className="text-xs text-[#9AA1B2] leading-relaxed">
                Includes high-priority inference queues, multi-model access, signed media asset hosting, and live webhook pipelines.
              </p>
            </div>

            {/* Compute Usage */}
            <div className="p-6 rounded-2xl bg-[#14161C] border border-[#262A35]">
              <div className="flex items-center justify-between text-xs text-[#9AA1B2] mb-3">
                <span className="font-mono uppercase tracking-wider">Queue Concurrency</span>
                <span className="text-xs font-mono text-[#E8EAF0]">1 / 5 slots</span>
              </div>
              <div className="text-xl font-bold text-[#E8EAF0] mb-2">Fair Usage Limit</div>
              <div className="w-full bg-[#1B1E26] h-2 rounded-full overflow-hidden mb-2 border border-[#262A35]">
                <div className="bg-[#7C5CFF] h-full rounded-full" style={{ width: "20%" }} />
              </div>
              <p className="text-xs text-[#9AA1B2]">Concurrent job limit per workspace.</p>
            </div>
          </div>

          {/* Model Pricing Reference */}
          <div className="rounded-2xl bg-[#14161C] border border-[#262A35] p-6 space-y-4">
            <h3 className="text-base font-semibold text-[#E8EAF0] flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-[#A995FF]" />
              Model Credit Rates
            </h3>
            <p className="text-xs text-[#9AA1B2]">
              Standardized credit costs calculated directly from upstream provider execution rates:
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-2">
              <div className="p-4 rounded-xl bg-[#0B0C10] border border-[#262A35]">
                <div className="text-xs font-mono text-[#A995FF] mb-1">Text to Image</div>
                <div className="text-sm font-semibold text-[#E8EAF0]">Flux 1.1 Pro / SDXL</div>
                <div className="text-xs text-[#9AA1B2] mt-2 font-mono">10 - 25 credits</div>
              </div>
              <div className="p-4 rounded-xl bg-[#0B0C10] border border-[#262A35]">
                <div className="text-xs font-mono text-[#A995FF] mb-1">Image to Image</div>
                <div className="text-sm font-semibold text-[#E8EAF0]">Flux Redux / Inpaint</div>
                <div className="text-xs text-[#9AA1B2] mt-2 font-mono">15 - 30 credits</div>
              </div>
              <div className="p-4 rounded-xl bg-[#0B0C10] border border-[#262A35]">
                <div className="text-xs font-mono text-[#A995FF] mb-1">Image to Video</div>
                <div className="text-sm font-semibold text-[#E8EAF0]">Kling / Minimax / Luma</div>
                <div className="text-xs text-[#9AA1B2] mt-2 font-mono">50 - 100 credits</div>
              </div>
              <div className="p-4 rounded-xl bg-[#0B0C10] border border-[#262A35]">
                <div className="text-xs font-mono text-[#A995FF] mb-1">Text to Video</div>
                <div className="text-sm font-semibold text-[#E8EAF0]">Luma Dream Machine</div>
                <div className="text-xs text-[#9AA1B2] mt-2 font-mono">60 - 120 credits</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === "general" && (
        <div className="rounded-2xl bg-[#14161C] border border-[#262A35] p-6 space-y-6 max-w-2xl">
          <h3 className="text-base font-semibold text-[#E8EAF0]">Workspace Details</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-[#9AA1B2] mb-1.5">
                Workspace Name
              </label>
              <input
                type="text"
                readOnly
                value={currentWorkspace?.name || "Personal Workspace"}
                className="w-full bg-[#0B0C10] border border-[#262A35] rounded-xl px-4 py-2.5 text-sm text-[#E8EAF0] focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[#9AA1B2] mb-1.5">
                Workspace ID
              </label>
              <input
                type="text"
                readOnly
                value={currentWorkspace?.id || "default"}
                className="w-full bg-[#0B0C10] border border-[#262A35] rounded-xl px-4 py-2.5 text-xs font-mono text-[#9AA1B2] focus:outline-none"
              />
            </div>
          </div>
        </div>
      )}

      {activeTab === "models" && (
        <div className="rounded-2xl bg-[#14161C] border border-[#262A35] p-6 space-y-4">
          <h3 className="text-base font-semibold text-[#E8EAF0]">Active AI Adapters</h3>
          <p className="text-xs text-[#9AA1B2]">
            Studio interfaces with multiple inference providers via unified protocol adapters.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
            <div className="p-4 rounded-xl bg-[#0B0C10] border border-[#262A35] flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-[#10B981] shrink-0 mt-0.5" />
              <div>
                <div className="text-sm font-semibold text-[#E8EAF0]">Replicate Adapter</div>
                <div className="text-xs text-[#9AA1B2] mt-0.5">Flux, SDXL, Stable Video</div>
              </div>
            </div>
            <div className="p-4 rounded-xl bg-[#0B0C10] border border-[#262A35] flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-[#10B981] shrink-0 mt-0.5" />
              <div>
                <div className="text-sm font-semibold text-[#E8EAF0]">Fal.ai Adapter</div>
                <div className="text-xs text-[#9AA1B2] mt-0.5">Fast Flux, Kling, Minimax</div>
              </div>
            </div>
            <div className="p-4 rounded-xl bg-[#0B0C10] border border-[#262A35] flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-[#10B981] shrink-0 mt-0.5" />
              <div>
                <div className="text-sm font-semibold text-[#E8EAF0]">Local / Fake Adapter</div>
                <div className="text-xs text-[#9AA1B2] mt-0.5">Development & Test Mock</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === "api" && (
        <div className="rounded-2xl bg-[#14161C] border border-[#262A35] p-6 space-y-4 max-w-2xl">
          <h3 className="text-base font-semibold text-[#E8EAF0]">API & Webhook Integrations</h3>
          <p className="text-xs text-[#9AA1B2]">
            All frontend interactions route through the authenticated FastAPI service with RFC 7807 error reporting and Supabase JWT verification.
          </p>
          <div className="p-4 rounded-xl bg-[#0B0C10] border border-[#262A35] flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-[#E8EAF0]">FastAPI OpenAPI Docs</div>
              <div className="text-xs font-mono text-[#9AA1B2]">http://localhost:8000/docs</div>
            </div>
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="px-3 py-1.5 rounded-lg bg-[#1B1E26] border border-[#262A35] text-xs font-medium text-[#A995FF] hover:text-[#E8EAF0] transition-colors flex items-center gap-1.5"
            >
              <span>Explore</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
