"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Check, ChevronDown } from "lucide-react";
import type { StudioModel } from "@/hooks/use-models";
import { providerAccent, providerLabel } from "@/lib/providers";

interface ModelPickerProps {
  models: StudioModel[];
  value: string | null;
  onChange: (slug: string) => void;
  /** Id of the visible label that names the picker. */
  labelledBy?: string;
  /** "compact" renders an inline pill for dense toolbars. */
  variant?: "default" | "compact";
}

interface ModelGroup {
  providerId: string;
  label: string;
  models: StudioModel[];
}

function costValue(model: StudioModel): number {
  const cost = Number(model.cost_credits);
  return Number.isFinite(cost) ? cost : Number.POSITIVE_INFINITY;
}

function formatCost(model: StudioModel): string {
  const cost = Number(model.cost_credits);
  if (!Number.isFinite(cost)) return model.cost_credits;
  return cost.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

/**
 * Group models by provider, cheapest first within each provider.
 * Provider groups are ordered alphabetically so the menu is stable.
 */
export function groupModelsByProvider(models: StudioModel[]): ModelGroup[] {
  const groups = new Map<string, StudioModel[]>();

  for (const model of models) {
    const providerModels = groups.get(model.provider_id) ?? [];
    providerModels.push(model);
    groups.set(model.provider_id, providerModels);
  }

  return Array.from(groups, ([providerId, providerModels]) => ({
    providerId,
    label: providerLabel(providerId),
    models: [...providerModels].sort((a, b) => {
      const costDelta = costValue(a) - costValue(b);
      if (Number.isFinite(costDelta) && costDelta !== 0) return costDelta;
      return a.display_name.localeCompare(b.display_name);
    }),
  })).sort((a, b) => a.label.localeCompare(b.label));
}

/**
 * Custom model combobox with provider-grouped options.
 *
 * Native <select> elements cannot style or pin provider labels, so this uses
 * a listbox with sticky provider headings that stay visible while scrolling.
 */
export function ModelPicker({
  models,
  value,
  onChange,
  labelledBy,
  variant = "default",
}: ModelPickerProps) {
  const compact = variant === "compact";
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  const listId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const groups = useMemo(() => groupModelsByProvider(models), [models]);
  const flatModels = useMemo(() => groups.flatMap((group) => group.models), [groups]);
  const selectedModel = models.find((model) => model.slug === value) ?? null;
  const selectedIndex = flatModels.findIndex((model) => model.slug === value);

  function openList() {
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : 0);
    setOpen(true);
  }

  function closeList(moveFocusToTrigger = false) {
    setOpen(false);
    if (moveFocusToTrigger) triggerRef.current?.focus();
  }

  function chooseModel(slug: string) {
    onChange(slug);
    closeList(true);
  }

  useEffect(() => {
    if (!open) return;
    listRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    optionRefs.current[activeIndex]?.scrollIntoView?.({ block: "nearest" });
  }, [open, activeIndex]);

  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [open]);

  function handleTriggerKeyDown(event: React.KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      openList();
      return;
    }

    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (open) closeList();
      else openList();
    }
  }

  function handleListKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    switch (event.key) {
      case "Escape":
        event.preventDefault();
        closeList(true);
        break;
      case "Tab":
        setOpen(false);
        break;
      case "ArrowDown":
        event.preventDefault();
        setActiveIndex((index) => Math.min(index + 1, flatModels.length - 1));
        break;
      case "ArrowUp":
        event.preventDefault();
        setActiveIndex((index) => Math.max(index - 1, 0));
        break;
      case "Home":
        event.preventDefault();
        setActiveIndex(0);
        break;
      case "End":
        event.preventDefault();
        setActiveIndex(flatModels.length - 1);
        break;
      case "Enter":
      case " ": {
        event.preventDefault();
        const model = flatModels[activeIndex];
        if (model) chooseModel(model.slug);
        break;
      }
      default:
        break;
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        role="combobox"
        id="composer-model"
        data-testid="model-picker-trigger"
        data-value={selectedModel?.slug ?? ""}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-labelledby={labelledBy}
        aria-label={labelledBy ? undefined : "Model"}
        onClick={() => (open ? closeList() : openList())}
        onKeyDown={handleTriggerKeyDown}
        className={`flex items-center justify-between text-left transition-colors hover:border-[#3A3F4D] focus:outline-none focus:ring-2 focus:ring-[#7C5CFF] ${
          compact
            ? "w-auto max-w-[15rem] gap-1.5 whitespace-nowrap rounded-lg border border-[#262A35] bg-[#0F1117] px-2.5 py-1.5"
            : "w-full gap-3 rounded-xl border border-[#262A35] bg-[#0F1117] px-3 py-2"
        }`}
      >
        {compact ? (
          <>
            <span
              className={`flex items-center gap-1.5 min-w-0 text-xs font-medium ${providerAccent(
                selectedModel?.provider_id ?? ""
              )}`}
            >
              <span className="h-3 w-1 rounded-full bg-current opacity-80" aria-hidden="true" />
              <span className="truncate text-[#E8EAF0]">
                {selectedModel?.display_name ?? "Select model"}
              </span>
            </span>
            <ChevronDown
              className={`h-3.5 w-3.5 shrink-0 text-[#9AA1B2] transition-transform ${
                open ? "rotate-180" : ""
              }`}
              aria-hidden="true"
            />
          </>
        ) : (
          <>
            <span className="flex min-w-0 flex-col">
              <span className="truncate text-sm text-[#E8EAF0]">
                {selectedModel?.display_name ?? "Select a model"}
              </span>
              {selectedModel && (
                <span
                  className={`mt-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] ${providerAccent(selectedModel.provider_id)}`}
                >
                  {providerLabel(selectedModel.provider_id)}
                </span>
              )}
            </span>
            <ChevronDown
              className={`h-4 w-4 shrink-0 text-[#9AA1B2] transition-transform ${open ? "rotate-180" : ""}`}
              aria-hidden="true"
            />
          </>
        )}
      </button>

      {open && (
        <div
          ref={listRef}
          id={listId}
          role="listbox"
          aria-labelledby={labelledBy}
          aria-activedescendant={flatModels.length > 0 ? `${listId}-option-${activeIndex}` : undefined}
          tabIndex={-1}
          onKeyDown={handleListKeyDown}
          className={`absolute z-30 max-h-80 overflow-y-auto rounded-xl border border-[#262A35] bg-[#0F1117] px-1 pb-1 shadow-2xl shadow-black/50 focus:outline-none ${
            compact ? "bottom-full mb-2 w-72 max-w-[calc(100vw-2rem)]" : "mt-2 w-full"
          }`}
        >
          {groups.map((group, groupIndex) => {
            const headingId = `${listId}-provider-${group.providerId}`;

            return (
              <div
                key={group.providerId}
                role="group"
                aria-labelledby={headingId}
                className={
                  groupIndex === 0 ? undefined : "mt-1.5 border-t border-[#262A35]/70 pt-1.5"
                }
              >
                <div
                  id={headingId}
                  data-testid={`model-provider-${group.providerId}`}
                  className={`sticky top-0 z-10 flex items-center justify-between bg-[#0F1117] px-2.5 py-2 text-[10px] font-bold uppercase tracking-[0.16em] ${providerAccent(
                    group.providerId
                  )}`}
                >
                  <span>{group.label}</span>
                  <span className="font-mono text-[10px] font-normal normal-case tracking-normal text-[#6B7280]">
                    {group.models.length}
                  </span>
                </div>

                <div className="space-y-0.5">
                  {group.models.map((model) => {
                    const index = flatModels.indexOf(model);
                    const isSelected = model.slug === value;
                    const isActive = index === activeIndex;

                    return (
                      <button
                        key={model.id}
                        ref={(element) => {
                          optionRefs.current[index] = element;
                        }}
                        type="button"
                        role="option"
                        id={`${listId}-option-${index}`}
                        aria-selected={isSelected}
                        tabIndex={-1}
                        onClick={() => chooseModel(model.slug)}
                        onMouseEnter={() => setActiveIndex(index)}
                        className={`flex w-full items-center justify-between gap-3 rounded-lg px-2.5 py-2 text-left text-sm transition-colors ${
                          isSelected
                            ? "bg-[#6C4CE8]/25 text-[#E8EAF0]"
                            : isActive
                              ? "bg-[#1B1E26] text-[#E8EAF0]"
                              : "text-[#C7CBD6] hover:bg-[#1B1E26]"
                        }`}
                      >
                        <span className="min-w-0 truncate">{model.display_name}</span>
                        <span className="flex shrink-0 items-center gap-2">
                          <span className="font-mono text-[11px] text-[#9AA1B2]">
                            {formatCost(model)} cr
                          </span>
                          {isSelected && (
                            <Check className="h-3.5 w-3.5 text-[#A995FF]" aria-hidden="true" />
                          )}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
