/** Shared formatting helpers for the settings screen. */

export function formatCredits(value: number | string | null | undefined): string {
  const numeric = typeof value === "string" ? Number(value) : value;
  if (numeric === null || numeric === undefined || !Number.isFinite(numeric)) {
    return "0";
  }
  return numeric.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function formatDelta(value: number | string): string {
  const numeric = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(numeric)) return "0";
  const magnitude = formatCredits(Math.abs(numeric));
  return numeric < 0 ? `−${magnitude}` : `+${magnitude}`;
}

export function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function shortId(value: string | null | undefined, length = 8): string {
  if (!value) return "—";
  return value.slice(0, length);
}

export const TASK_LABELS: Record<string, string> = {
  text_to_image: "Text to image",
  image_to_image: "Image to image",
  text_to_video: "Text to video",
  image_to_video: "Image to video",
};

export { PROVIDER_LABELS } from "@/lib/providers";
