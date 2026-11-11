import { createServerClient, type CookieOptions } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL || "http://127.0.0.1:54321",
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "dummy-anon-key",
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet: { name: string; value: string; options: CookieOptions }[]) {
          // The request cookie jar is mutated first so the refreshed cookies are
          // forwarded to the route handler, then copied onto the response.
          cookiesToSet.forEach(({ name, value }) => {
            request.cookies.set(name, value);
          });
          response = NextResponse.next({ request });

          cookiesToSet.forEach(({ name, value, options }) => {
            response.cookies.set(name, value, options);
          });
        },
      },
    }
  );

  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Preserve any cookies refreshed by getUser() when we return a redirect,
  // otherwise a rotated refresh token would be lost and the user could be
  // signed out on the next request.
  const redirectTo = (url: URL) => {
    const redirectResponse = NextResponse.redirect(url);
    for (const cookie of response.cookies.getAll()) {
      redirectResponse.cookies.set(cookie);
    }
    return redirectResponse;
  };

  const isAuthPage = request.nextUrl.pathname.startsWith("/login");
  const isProtectedPage =
    request.nextUrl.pathname.startsWith("/projects") ||
    request.nextUrl.pathname === "/";

  // Redirect unauthenticated user to login if accessing protected route
  if (!user && isProtectedPage) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("redirectedFrom", request.nextUrl.pathname);
    return redirectTo(url);
  }

  // Redirect authenticated user from login to projects
  if (user && isAuthPage) {
    const url = request.nextUrl.clone();
    url.pathname = "/projects";
    return redirectTo(url);
  }

  // Redirect root / to /projects
  if (user && request.nextUrl.pathname === "/") {
    const url = request.nextUrl.clone();
    url.pathname = "/projects";
    return redirectTo(url);
  }

  return response;
}
