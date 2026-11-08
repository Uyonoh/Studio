import { type APIRequestContext } from "@playwright/test";

export const SUPABASE_URL = "http://127.0.0.1:3101";
export const STORAGE_KEY = `sb-${new URL(SUPABASE_URL).hostname.split(".")[0]}-auth-token`;

/** Build the Supabase session cookie that the middleware expects. */
export function makeSessionCookie() {
  const session = {
    access_token: "e2e-access-token",
    token_type: "bearer",
    expires_in: 3600,
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    refresh_token: "e2e-refresh-token",
    user: {
      id: "usr-e2e-123",
      aud: "authenticated",
      role: "authenticated",
      email: "e2e@example.com",
    },
  };
  const encoded = Buffer.from(JSON.stringify(session)).toString("base64url");
  return {
    name: STORAGE_KEY,
    value: `base64-${encoded}`,
    domain: "127.0.0.1",
    path: "/",
    httpOnly: false,
    secure: false,
    sameSite: "Lax" as const,
  };
}

/**
 * Restore the mock backend to its seeded fixture.
 *
 * The dev server starts one mock process for the whole Playwright run, so
 * without this each spec would inherit jobs/projects created by earlier specs.
 */
export async function resetMockBackend(request: APIRequestContext): Promise<void> {
  const response = await request.post(`${SUPABASE_URL}/__test__/reset`);
  if (!response.ok()) {
    throw new Error(`Mock backend reset failed with HTTP ${response.status()}`);
  }
}
