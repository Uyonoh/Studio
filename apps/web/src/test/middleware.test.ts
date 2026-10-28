import { describe, it, expect, vi } from "vitest";
import { updateSession } from "@/lib/supabase/middleware";
import { NextRequest } from "next/server";

let mockUser: any = null;

vi.mock("@supabase/ssr", () => ({
  createServerClient: () => ({
    auth: {
      getUser: vi.fn().mockImplementation(async () => ({
        data: { user: mockUser },
        error: null,
      })),
    },
  }),
}));

describe("Middleware auth protection", () => {
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
});
