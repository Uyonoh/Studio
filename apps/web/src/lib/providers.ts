/** Human-readable provider names for model catalog UIs. */

export const PROVIDER_LABELS: Record<string, string> = {
  replicate: "Replicate",
  fal: "Fal.ai",
  google: "Google AI",
  fake: "Deterministic Test Provider",
};

/** Accent color used for a provider's group heading in the model picker. */
export const PROVIDER_ACCENTS: Record<string, string> = {
  replicate: "text-[#F5C451]",
  fal: "text-[#A995FF]",
  google: "text-[#7DD3FC]",
  fake: "text-[#9AA1B2]",
};

export function providerLabel(providerId: string): string {
  return PROVIDER_LABELS[providerId] ?? providerId;
}

export function providerAccent(providerId: string): string {
  return PROVIDER_ACCENTS[providerId] ?? "text-[#C7CBD6]";
}
