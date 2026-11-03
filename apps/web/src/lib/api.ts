import { createClient as createStudioClient, type ApiClient } from "@studio/api-client";
import { createClient as createBrowserSupabase } from "@/lib/supabase/client";

let browserApiClient: ApiClient | null = null;

export function getApiClient(): ApiClient {
  if (typeof window === "undefined") {
    // Server-side
    return createStudioClient(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000");
  }

  if (!browserApiClient) {
    const supabase = createBrowserSupabase();
    browserApiClient = createStudioClient(
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
      async () => {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        return session?.access_token ?? null;
      }
    );
  }

  return browserApiClient;
}

export const api = getApiClient();
