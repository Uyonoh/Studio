"use client";

import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Building2,
  CreditCard,
  Cpu,
  Key,
  type LucideIcon,
} from "lucide-react";
import { useCurrentWorkspace } from "@/components/providers/workspace-context";
import { ApiPanel } from "@/components/settings/api-panel";
import { GeneralPanel } from "@/components/settings/general-panel";
import { ModelsPanel } from "@/components/settings/models-panel";
import { UsagePanel } from "@/components/settings/usage-panel";

type SettingsTab = "usage" | "general" | "models" | "api";

const TABS: Array<{ id: SettingsTab; label: string; icon: LucideIcon; panelId: string }> = [
  { id: "usage", label: "Usage & Billing", icon: CreditCard, panelId: "settings-panel-usage" },
  { id: "general", label: "General", icon: Building2, panelId: "settings-panel-general" },
  { id: "models", label: "AI Models & Providers", icon: Cpu, panelId: "settings-panel-models" },
  { id: "api", label: "API & Webhooks", icon: Key, panelId: "settings-panel-api" },
];

const TAB_DESCRIPTIONS: Record<SettingsTab, string> = {
  usage: "Track your credit balance, recent spend, and every ledger entry.",
  general: "Manage workspace identity and access details.",
  models: "Review the models and providers available to this workspace.",
  api: "Connection details and authentication for the Studio API.",
};

function normalizeTab(value: string | null): SettingsTab {
  // "billing" was the previous tab id; keep old links working.
  if (value === "billing") return "usage";
  if (value === "general" || value === "models" || value === "api") return value;
  return "usage";
}

function SettingsContent() {
  const { currentWorkspace } = useCurrentWorkspace();
  const searchParams = useSearchParams();
  const router = useRouter();

  const activeTab = normalizeTab(searchParams.get("tab"));

  const handleTabChange = (tab: SettingsTab) => {
    if (tab === activeTab) return;
    router.replace(`/settings?tab=${tab}`, { scroll: false });
  };

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      {/* Page header */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-[#E8EAF0]">
              Workspace &amp; Settings
            </h1>
            <span className="rounded-full border border-[#262A35] bg-[#1B1E26] px-2.5 py-0.5 text-xs font-mono text-[#A995FF]">
              {currentWorkspace?.name || "Active workspace"}
            </span>
          </div>
          <p className="mt-1 text-sm text-[#9AA1B2]">{TAB_DESCRIPTIONS[activeTab]}</p>
        </div>
      </div>

      {/* Tabs */}
      <div
        role="tablist"
        aria-label="Settings sections"
        className="flex items-center gap-6 overflow-x-auto border-b border-[#262A35]"
      >
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              id={`settings-tab-${tab.id}`}
              aria-selected={isActive}
              aria-controls={tab.panelId}
              onClick={() => handleTabChange(tab.id)}
              className={`flex shrink-0 items-center gap-2 border-b-2 pb-3 text-sm font-medium transition-colors ${
                isActive
                  ? "border-[#7C5CFF] font-semibold text-[#E8EAF0]"
                  : "border-transparent text-[#9AA1B2] hover:text-[#E8EAF0]"
              }`}
            >
              <Icon className={`h-4 w-4 ${isActive ? "text-[#A995FF]" : ""}`} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Panels */}
      {TABS.map((tab) => (
        <section
          key={tab.id}
          id={tab.panelId}
          role="tabpanel"
          aria-labelledby={`settings-tab-${tab.id}`}
          hidden={activeTab !== tab.id}
        >
          {activeTab === tab.id && (
            <>
              {tab.id === "usage" && (
                <div id="usage">
                  <UsagePanel workspaceId={currentWorkspace?.id} />
                </div>
              )}
              {tab.id === "general" && <GeneralPanel />}
              {tab.id === "models" && <ModelsPanel />}
              {tab.id === "api" && <ApiPanel />}
            </>
          )}
        </section>
      ))}
    </div>
  );
}

function SettingsFallback() {
  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <div className="space-y-2">
        <div className="h-7 w-64 animate-pulse rounded-lg bg-[#14161C]" />
        <div className="h-4 w-96 animate-pulse rounded bg-[#14161C]" />
      </div>
      <div className="h-10 w-full animate-pulse rounded-lg border border-[#262A35] bg-[#14161C]" />
      <div className="h-48 w-full animate-pulse rounded-2xl border border-[#262A35] bg-[#14161C]" />
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={<SettingsFallback />}>
      <SettingsContent />
    </Suspense>
  );
}
