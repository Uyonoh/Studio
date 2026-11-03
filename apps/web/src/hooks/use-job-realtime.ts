"use client";

import { useEffect, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";

export type RealtimeConnectionState = "connecting" | "subscribed" | "disconnected";

/** Subset of a `generation_jobs` row delivered by Supabase Realtime. */
export interface GenerationJobRow {
  id: string;
  status: string;
  error_code: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export const DEFAULT_SUBSCRIBE_TIMEOUT_MS = 5_000;

/**
 * Subscribe to `generation_jobs` changes for one project.
 *
 * Returns the connection state so callers can fall back to polling when the
 * channel is not subscribed in time or drops. The subscription is always
 * removed on unmount or when the project changes, so navigating between
 * projects never accumulates duplicate channels.
 */
export function useJobRealtime(
  projectId: string | null | undefined,
  onJobChange: (row: GenerationJobRow) => void,
  subscribeTimeoutMs: number = DEFAULT_SUBSCRIBE_TIMEOUT_MS
): RealtimeConnectionState {
  const [state, setState] = useState<RealtimeConnectionState>(
    projectId ? "connecting" : "disconnected"
  );
  const callbackRef = useRef(onJobChange);

  useEffect(() => {
    callbackRef.current = onJobChange;
  }, [onJobChange]);

  useEffect(() => {
    if (!projectId) {
      setState("disconnected");
      return;
    }

    setState("connecting");
    const supabase = createClient();
    let settled = false;

    const timeout = setTimeout(() => {
      if (!settled) {
        settled = true;
        setState("disconnected");
      }
    }, subscribeTimeoutMs);

    const channel = supabase
      .channel(`generation-jobs:${projectId}`)
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "generation_jobs",
          filter: `project_id=eq.${projectId}`,
        },
        (payload) => {
          const row = payload.new as GenerationJobRow | undefined;
          if (row?.id) callbackRef.current(row);
        }
      )
      .subscribe((status) => {
        if (status === "SUBSCRIBED") {
          settled = true;
          clearTimeout(timeout);
          setState("subscribed");
        } else if (status === "CHANNEL_ERROR" || status === "TIMED_OUT" || status === "CLOSED") {
          settled = true;
          clearTimeout(timeout);
          setState("disconnected");
        }
      });

    return () => {
      clearTimeout(timeout);
      void supabase.removeChannel(channel);
    };
  }, [projectId, subscribeTimeoutMs]);

  return state;
}
