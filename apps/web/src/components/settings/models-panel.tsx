"use client";

import { AlertCircle, Cpu, Loader2 } from "lucide-react";
import { useModels } from "@/hooks/use-models";
import { PROVIDER_LABELS, TASK_LABELS, formatCredits } from "./format";

export function ModelsPanel() {
  const { data: models, isLoading, isError, error, refetch } = useModels();

  const providers = Array.from(new Set((models ?? []).map((model) => model.provider_id)));

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-[#262A35] bg-[#14161C] p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-[#E8EAF0]">Available models</h3>
            <p className="mt-1 text-xs text-[#9AA1B2]">
              Enabled models and their credit cost, read live from the model registry.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded-full border border-[#262A35] bg-[#1B1E26] px-2.5 py-1 text-xs font-mono text-[#A995FF]">
              {models?.length ?? 0} models
            </span>
            <span className="rounded-full border border-[#262A35] bg-[#1B1E26] px-2.5 py-1 text-xs font-mono text-[#9AA1B2]">
              {providers.length} provider{providers.length === 1 ? "" : "s"}
            </span>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center gap-2 rounded-2xl border border-[#262A35] bg-[#14161C] px-5 py-12 text-sm text-[#9AA1B2]">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading models…
        </div>
      ) : isError ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-[#262A35] bg-[#14161C] px-5 py-12 text-center">
          <AlertCircle className="h-6 w-6 text-[#F87171]" />
          <p className="text-sm text-[#E8EAF0]">
            {error instanceof Error ? error.message : "Could not load models."}
          </p>
          <button
            type="button"
            onClick={() => refetch()}
            className="rounded-lg border border-[#262A35] bg-[#1B1E26] px-3 py-1.5 text-xs font-medium text-[#A995FF] transition-colors hover:text-[#E8EAF0]"
          >
            Try again
          </button>
        </div>
      ) : !models || models.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-2xl border border-[#262A35] bg-[#14161C] px-5 py-12 text-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#262A35] bg-[#1B1E26]">
            <Cpu className="h-5 w-5 text-[#A995FF]" />
          </div>
          <p className="text-sm font-medium text-[#E8EAF0]">No models are enabled</p>
          <p className="max-w-sm text-xs text-[#9AA1B2]">
            Enable at least one provider model in the registry to start generating.
          </p>
        </div>
      ) : (
        <div className="space-y-5">
          {providers.map((providerId) => {
            const providerModels = (models ?? []).filter(
              (model) => model.provider_id === providerId
            );
            return (
              <div
                key={providerId}
                className="overflow-hidden rounded-2xl border border-[#262A35] bg-[#14161C]"
              >
                <div className="flex items-center justify-between border-b border-[#262A35] px-5 py-3">
                  <h4 className="text-sm font-semibold text-[#E8EAF0]">
                    {PROVIDER_LABELS[providerId] ?? providerId}
                  </h4>
                  <span className="font-mono text-[11px] text-[#9AA1B2]">
                    {providerModels.length} model{providerModels.length === 1 ? "" : "s"}
                  </span>
                </div>
                <ul className="divide-y divide-[#262A35]">
                  {providerModels.map((model) => (
                    <li
                      key={model.id}
                      className="flex flex-col gap-2 px-5 py-3.5 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium text-[#E8EAF0]">
                          {model.display_name}
                        </div>
                        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-[#9AA1B2]">
                          <span className="font-mono">{model.slug}</span>
                          <span aria-hidden="true">·</span>
                          <span>{TASK_LABELS[model.task_type] ?? model.task_type}</span>
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <span className="rounded-full border border-[#262A35] bg-[#0B0C10] px-2.5 py-1 font-mono text-xs text-[#E8EAF0]">
                          {formatCredits(model.cost_credits)} credits
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
