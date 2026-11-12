"use client";

import { useState } from "react";
import { Check, Copy, ExternalLink, KeyRound, Server, Webhook } from "lucide-react";
import { toast } from "sonner";

const DEFAULT_API_URL = "http://localhost:8000";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL).replace(/\/$/, "");

function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(value);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1500);
      } else {
        toast.error("Clipboard access is not available in this browser.");
      }
    } catch {
      toast.error("Could not copy to the clipboard.");
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={`Copy ${label}`}
      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[#262A35] bg-[#1B1E26] text-[#9AA1B2] transition-colors hover:text-[#E8EAF0]"
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-emerald-400" />
      ) : (
        <Copy className="h-3.5 w-3.5" />
      )}
    </button>
  );
}

function EndpointRow({
  icon: Icon,
  title,
  description,
  value,
  href,
}: {
  icon: typeof Server;
  title: string;
  description: string;
  value: string;
  href?: string;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-[#262A35] bg-[#0B0C10] p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[#262A35] bg-[#1B1E26]">
          <Icon className="h-4 w-4 text-[#A995FF]" />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-medium text-[#E8EAF0]">{title}</div>
          <div className="mt-0.5 break-all font-mono text-xs text-[#9AA1B2]">{value}</div>
          <p className="mt-1 text-xs text-[#9AA1B2]">{description}</p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2 self-end sm:self-auto">
        <CopyButton value={value} label={title} />
        {href && (
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            aria-label={`Open ${title}`}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#262A35] bg-[#1B1E26] text-[#A995FF] transition-colors hover:text-[#E8EAF0]"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </div>
    </div>
  );
}

export function ApiPanel() {
  return (
    <div className="max-w-3xl space-y-6">
      <div className="rounded-2xl border border-[#262A35] bg-[#14161C] p-6">
        <h3 className="text-base font-semibold text-[#E8EAF0]">API & integrations</h3>
        <p className="mt-1 text-xs leading-relaxed text-[#9AA1B2]">
          All frontend requests are sent to the authenticated FastAPI service. The service verifies
          the Supabase access token, returns RFC 7807 problem details on errors, and scopes data to
          the active workspace.
        </p>

        <div className="mt-5 space-y-3">
          <EndpointRow
            icon={Server}
            title="API base URL"
            description="Base URL used by the Studio web client."
            value={API_URL}
          />
          <EndpointRow
            icon={KeyRound}
            title="OpenAPI schema"
            description="Machine-readable contract for the API (requires a bearer token to call endpoints)."
            value={`${API_URL}/openapi.json`}
            href={`${API_URL}/openapi.json`}
          />
          <EndpointRow
            icon={Server}
            title="Interactive docs"
            description="Swagger UI for exploring and trying endpoints."
            value={`${API_URL}/docs`}
            href={`${API_URL}/docs`}
          />
          <EndpointRow
            icon={Webhook}
            title="Webhook receiver"
            description="Internal endpoint used by providers to report job completion."
            value={`${API_URL}/internal/webhooks/{provider}/{job_id}`}
          />
        </div>
      </div>

      <div className="rounded-2xl border border-[#262A35] bg-[#14161C] p-6">
        <h4 className="text-sm font-semibold text-[#E8EAF0]">Authentication</h4>
        <p className="mt-1 text-xs leading-relaxed text-[#9AA1B2]">
          Requests must include an <span className="font-mono text-[#A995FF]">Authorization</span>{" "}
          header with a Supabase-issued bearer token. The web client refreshes tokens automatically
          from your signed-in session; there are no long-lived API keys to manage on this screen.
        </p>
      </div>
    </div>
  );
}
