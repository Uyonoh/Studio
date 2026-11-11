// @vitest-environment node
import { describe, it, expect, vi, beforeEach } from "vitest";
import { updateSession } from "@/lib/supabase/middleware";
import { NextRequest } from "next/server";

let mockUser: any = null;
let mockRefreshedCookies: { name: string; value: string; options?: any }[] = [];

vi.mock("@supabase/ssr", () => ({
  createServerClient: (_url: string, _key: string, options: any) => ({
    auth: {
      getUser: vi.fn().mockImplementation(async () => {
        if (mockRefreshedCookies.length > 0) {
          options.cookies.setAll(mockRefreshedCookies);
        }
        return {
          data: { user: mockUser },
          error: null,
        };
      }),
    },
  }),
}));

describe("Middleware auth protection", () => {
  beforeEach(() => {
    mockRefreshedCookies = [];
  });

  it("redirects unauthenticated user from /projects to /login", async () => {
    mockUser = null;
    const req = new NextRequest("http://localhost:3000/projects");
    const res = await updateSession(req);

    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/login?redirectedFrom=%2Fprojects");
  });

  it("redirects unauthenticated user from / to /login", async () => {
    mockUser = null;
    const req = new NextRequest("http://localhost:3000/");
    const res = await updateSession(req);

    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/login?redirectedFrom=%2F");
  });

  it("allows unauthenticated user to access /login", async () => {
    mockUser = null;
    const req = new NextRequest("http://localhost:3000/login");
    const res = await updateSession(req);

    expect(res.status).toBe(200);
  });

  it("redirects authenticated user from /login to /projects", async () => {
    mockUser = { id: "user-123", email: "user@example.com" };
    const req = new NextRequest("http://localhost:3000/login");
    const res = await updateSession(req);

    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/projects");
  });

  it("allows authenticated user to access /projects", async () => {
    mockUser = { id: "user-123", email: "user@example.com" };
    const req = new NextRequest("http://localhost:3000/projects");
    const res = await updateSession(req);

    expect(res.status).toBe(200);
  });

  it("copies every refreshed auth cookie onto the response", async () => {
    mockUser = { id: "user-123", email: "user@example.com" };
    mockRefreshedCookies = [
      { name: "sb-access-token.0", value: "chunk-0" },
      { name: "sb-access-token.1", value: "chunk-1" },
      { name: "sb-refresh-token", value: "refresh-token" },
    ];

    const req = new NextRequest("http://localhost:3000/projects");
    const res = await updateSession(req);

    expect(res.cookies.get("sb-access-token.0")?.value).toBe("chunk-0");
    expect(res.cookies.get("sb-access-token.1")?.value).toBe("chunk-1");
    expect(res.cookies.get("sb-refresh-token")?.value).toBe("refresh-token");
  });

  it("keeps refreshed cookies when returning a redirect", async () => {
    mockUser = { id: "user-123", email: "user@example.com" };
    mockRefreshedCookies = [
      { name: "sb-refresh-token", value: "rotated-refresh-token" },
    ];

    const req = new NextRequest("http://localhost:3000/login");
    const res = await updateSession(req);

    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/projects");
    expect(res.cookies.get("sb-refresh-token")?.value).toBe(
      "rotated-refresh-token"
    );
  });
});
