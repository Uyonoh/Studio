import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import LoginPage from "@/app/login/page";

const mockSignInWithOtp = vi.fn();
const mockSignInWithOAuth = vi.fn();

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      signInWithOtp: mockSignInWithOtp,
      signInWithOAuth: mockSignInWithOAuth,
    },
  }),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders branding, headings and accessible inputs", () => {
    render(<LoginPage />);

    expect(screen.getByRole("heading", { name: /studio/i })).toBeInTheDocument();
    expect(screen.getByText(/create images and videos with ai/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /continue with google/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/work email/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send magic link/i })).toBeInTheDocument();
  });

  it("submits email magic link successfully and displays confirmation", async () => {
    mockSignInWithOtp.mockResolvedValueOnce({ error: null });

    render(<LoginPage />);

    const emailInput = screen.getByLabelText(/work email/i);
    fireEvent.change(emailInput, { target: { value: "creator@example.com" } });

    const submitBtn = screen.getByRole("button", { name: /send magic link/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockSignInWithOtp).toHaveBeenCalledWith({
        email: "creator@example.com",
        options: {
          emailRedirectTo: expect.stringContaining("/auth/callback"),
        },
      });
    });

    expect(
      await screen.findByText(/check your inbox! we sent a magic sign-in link/i)
    ).toBeInTheDocument();
  });

  it("triggers Google OAuth when Continue with Google is clicked", async () => {
    mockSignInWithOAuth.mockResolvedValueOnce({ error: null });

    render(<LoginPage />);

    const googleBtn = screen.getByRole("button", { name: /continue with google/i });
    fireEvent.click(googleBtn);

    await waitFor(() => {
      expect(mockSignInWithOAuth).toHaveBeenCalledWith({
        provider: "google",
        options: {
          redirectTo: expect.stringContaining("/auth/callback"),
        },
      });
    });
  });

  it("displays error message when sign in fails", async () => {
    mockSignInWithOtp.mockResolvedValueOnce({
      error: { message: "Invalid email address" },
    });

    render(<LoginPage />);

    const emailInput = screen.getByLabelText(/work email/i);
    fireEvent.change(emailInput, { target: { value: "invalid@example.com" } });

    const submitBtn = screen.getByRole("button", { name: /send magic link/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockSignInWithOtp).toHaveBeenCalled();
    });

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email address");
  });
});
