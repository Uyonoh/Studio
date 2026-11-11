import type { EmailOtpType } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase/server";
import { safeRedirectPath } from "@/lib/safe-redirect";
import { NextResponse, type NextRequest } from "next/server";

/**
 * Resolve the public origin for redirects. On Vercel/Render the request URL is
 * the internal one, so prefer the forwarded host outside local development.
 */
function getRedirectOrigin(request: NextRequest): string {
  const { origin } = new URL(request.url);
  const forwardedHost = request.headers.get("x-forwarded-host");
  const forwardedProto = request.headers.get("x-forwarded-proto");

  if (process.env.NODE_ENV === "development" || !forwardedHost) {
    return origin;
  }

  return `${forwardedProto ?? "https"}://${forwardedHost}`;
}

function loginErrorUrl(origin: string, message: string): NextResponse {
  const url = new URL("/login", origin);
  url.searchParams.set("error", message);
  return NextResponse.redirect(url);
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const origin = getRedirectOrigin(request);
  const next = safeRedirectPath(searchParams.get("next"));

  // Supabase / OAuth providers can return an error instead of a code, e.g.
  // access_denied or bad_oauth_state.
  const providerError =
    searchParams.get("error_description") ??
    searchParams.get("error_code") ??
    searchParams.get("error");

  if (providerError) {
    return loginErrorUrl(origin, providerError);
  }

  const code = searchParams.get("code");
  const tokenHash = searchParams.get("token_hash");
  const otpType = searchParams.get("type") as EmailOtpType | null;

  const supabase = createClient();

  // PKCE flow: Google OAuth and the default magic-link email template.
  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(new URL(next, origin));
    }
  }

  // Token-hash flow: used by custom email templates that link directly to
  // /auth/callback?token_hash=...&type=magiclink.
  if (tokenHash && otpType) {
    const { error } = await supabase.auth.verifyOtp({
      type: otpType,
      token_hash: tokenHash,
    });
    if (!error) {
      return NextResponse.redirect(new URL(next, origin));
    }
  }

  return loginErrorUrl(origin, "auth_callback_failed");
}
