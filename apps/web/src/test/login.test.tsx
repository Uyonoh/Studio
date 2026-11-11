import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import LoginPage from "@/app/login/page";

const mockSignInWithOtp = vi.fn();
const mockSignInWithOAuth = vi.fn();
const mockSignInWithPassword = vi.fn();
const mockPush = vi.fn();
const mockRefresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    refresh: mockRefresh,
  }),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      signInWithOtp: mockSignInWithOtp,
      signInWithOAuth: mockSignInWithOAuth,
      signInWithPassword: mockSignInWithPassword,
    },
  }),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, "", "/login");
  });

  it("renders branding, headings and accessible inputs", () => {
    render(<LoginPage />);

    expect(screen.getByRole("heading", { name: /studio/i })).toBeInTheDocument();
    expect(screen.getByText(/create images and videos with ai/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /continue with google/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/work email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /password/i })).toHaveAttribute(
      "aria-selected",
      "true"
    );
    expect(screen.getByRole("tab", { name: /magic link/i })).toHaveAttribute(
      "aria-selected",
      "false"
    );
  });

  it("submits email magic link successfully and displays confirmation", async () => {
    mockSignInWithOtp.mockResolvedValueOnce({ error: null });

    render(<LoginPage />);

    fireEvent.click(screen.getByRole("tab", { name: /magic link/i }));

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

    fireEvent.click(screen.getByRole("tab", { name: /magic link/i }));

    const emailInput = screen.getByLabelText(/work email/i);
    fireEvent.change(emailInput, { target: { value: "invalid@example.com" } });

    const submitBtn = screen.getByRole("button", { name: /send magic link/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockSignInWithOtp).toHaveBeenCalled();
    });

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email address");
  });

  it("signs in with email and password by default", async () => {
    mockSignInWithPassword.mockResolvedValueOnce({ error: null });

    render(<LoginPage />);

    expect(screen.getByRole("tab", { name: /password/i })).toHaveAttribute(
      "aria-selected",
      "true"
    );
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();

    const emailInput = screen.getByLabelText(/work email/i);
    const passwordInput = screen.getByLabelText(/password/i);

    fireEvent.change(emailInput, { target: { value: "dev@example.com" } });
    fireEvent.change(passwordInput, { target: { value: "DevPassword123!" } });

    const submitBtn = screen.getByRole("button", { name: /sign in/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockSignInWithPassword).toHaveBeenCalledWith({
        email: "dev@example.com",
        password: "DevPassword123!",
      });
      expect(mockPush).toHaveBeenCalledWith("/projects");
    });
  });

  it("switches to magic link mode as a secondary option", () => {
    render(<LoginPage />);

    fireEvent.click(screen.getByRole("tab", { name: /magic link/i }));

    expect(screen.getByRole("tab", { name: /magic link/i })).toHaveAttribute(
      "aria-selected",
      "true"
    );
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send magic link/i })).toBeInTheDocument();
  });

  it("carries redirectedFrom through the magic-link callback", async () => {
    window.history.replaceState(
      {},
      "",
      "/login?redirectedFrom=%2Fprojects%2Fproj-1"
    );
    mockSignInWithOtp.mockResolvedValueOnce({ error: null });

    render(<LoginPage />);

    fireEvent.click(screen.getByRole("tab", { name: /magic link/i }));

    fireEvent.change(screen.getByLabelText(/work email/i), {
      target: { value: "creator@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send magic link/i }));

    await waitFor(() => {
      expect(mockSignInWithOtp).toHaveBeenCalledWith({
        email: "creator@example.com",
        options: {
          emailRedirectTo: expect.stringContaining(
            "/auth/callback?next=%2Fprojects%2Fproj-1"
          ),
        },
      });
    });
  });

  it("carries redirectedFrom through the Google callback", async () => {
    window.history.replaceState(
      {},
      "",
      "/login?redirectedFrom=%2Fprojects%2Fproj-1"
    );
    mockSignInWithOAuth.mockResolvedValueOnce({ error: null });

    render(<LoginPage />);
    fireEvent.click(screen.getByRole("button", { name: /continue with google/i }));

    await waitFor(() => {
      expect(mockSignInWithOAuth).toHaveBeenCalledWith({
        provider: "google",
        options: {
          redirectTo: expect.stringContaining(
            "/auth/callback?next=%2Fprojects%2Fproj-1"
          ),
        },
      });
    });
  });

  it("does not honor an external redirectedFrom destination", async () => {
    window.history.replaceState(
      {},
      "",
      "/login?redirectedFrom=https%3A%2F%2Fevil.example.com"
    );
    mockSignInWithPassword.mockResolvedValueOnce({ error: null });

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText(/work email/i), {
      target: { value: "dev@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "DevPassword123!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/projects");
    });
  });

  it("shows a friendly message for OAuth access_denied errors", async () => {
    window.history.replaceState({}, "", "/login?error=access_denied");

    render(<LoginPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /cancelled or access was denied/i
    );
  });

  it("shows an expired-link message for auth_callback_failed", async () => {
    window.history.replaceState({}, "", "/login?error=auth_callback_failed");

    render(<LoginPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /invalid or has expired/i
    );
  });
});
