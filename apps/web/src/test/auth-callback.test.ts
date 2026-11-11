import { describe, it, expect, vi, beforeEach } from "vitest";
import { GET } from "@/app/auth/callback/route";

const { mockExchangeCodeForSession, mockVerifyOtp } = vi.hoisted(() => ({
  mockExchangeCodeForSession: vi.fn(),
  mockVerifyOtp: vi.fn(),
}));

vi.mock("@/lib/supabase/server", () => ({
  createClient: () => ({
    auth: {
      exchangeCodeForSession: mockExchangeCodeForSession,
      verifyOtp: mockVerifyOtp,
    },
  }),
}));

function callbackRequest(query: string): Request {
  return new Request(`http://localhost:3000/auth/callback${query}`);
}

function locationOf(response: Response): URL {
  return new URL(response.headers.get("location") ?? "");
}

describe("auth callback route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("exchanges a PKCE code and redirects to /projects", async () => {
    mockExchangeCodeForSession.mockResolvedValueOnce({ error: null });

    const response = await GET(callbackRequest("?code=valid-code") as never);

    expect(mockExchangeCodeForSession).toHaveBeenCalledWith("valid-code");
    expect(response.status).toBe(307);
    expect(locationOf(response).pathname).toBe("/projects");
  });

  it("preserves a safe next destination", async () => {
    mockExchangeCodeForSession.mockResolvedValueOnce({ error: null });

    const response = await GET(
      callbackRequest("?code=valid-code&next=%2Fprojects%2Fproj-1") as never
    );

    expect(locationOf(response).pathname).toBe("/projects/proj-1");
  });

  it("rejects external next destinations", async () => {
    mockExchangeCodeForSession.mockResolvedValueOnce({ error: null });

    const response = await GET(
      callbackRequest("?code=valid-code&next=%2F%2Fevil.example.com") as never
    );

    expect(locationOf(response).pathname).toBe("/projects");
    expect(locationOf(response).host).toBe("localhost:3000");
  });

  it("verifies token_hash magic links from custom email templates", async () => {
    mockVerifyOtp.mockResolvedValueOnce({ error: null });

    const response = await GET(
      callbackRequest("?token_hash=abc123&type=magiclink&next=%2Fprojects") as never
    );

    expect(mockVerifyOtp).toHaveBeenCalledWith({
      type: "magiclink",
      token_hash: "abc123",
    });
    expect(locationOf(response).pathname).toBe("/projects");
  });

  it("redirects back to login when the code exchange fails", async () => {
    mockExchangeCodeForSession.mockResolvedValueOnce({
      error: { message: "invalid flow state" },
    });

    const response = await GET(callbackRequest("?code=expired-code") as never);

    expect(locationOf(response).pathname).toBe("/login");
    expect(locationOf(response).searchParams.get("error")).toBe(
      "auth_callback_failed"
    );
  });

  it("surfaces provider errors such as access_denied", async () => {
    const response = await GET(
      callbackRequest(
        "?error=access_denied&error_description=User+denied+access"
      ) as never
    );

    expect(locationOf(response).pathname).toBe("/login");
    expect(locationOf(response).searchParams.get("error")).toBe(
      "User denied access"
    );
    expect(mockExchangeCodeForSession).not.toHaveBeenCalled();
  });

  it("redirects to login when the callback has no code or token", async () => {
    const response = await GET(callbackRequest("") as never);

    expect(locationOf(response).pathname).toBe("/login");
    expect(locationOf(response).searchParams.get("error")).toBe(
      "auth_callback_failed"
    );
  });
});
