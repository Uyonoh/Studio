import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { Sidebar } from "@/components/layout/sidebar";
import { TopBar } from "@/components/layout/top-bar";
import { WorkspaceSwitcher } from "@/components/layout/workspace-switcher";
import { AppShell } from "@/components/layout/app-shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/projects",
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      signOut: vi.fn().mockResolvedValue({ error: null }),
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
    },
  }),
}));

vi.mock("@/hooks/use-credits", () => ({
  useCreditBalance: () => ({ data: 1000, isLoading: false }),
}));

describe("Layout Components", () => {
  it("renders workspace switcher with current workspace and toggles options", () => {
    const workspaces = [
      { id: "ws-1", name: "Alpha Workspace" },
      { id: "ws-2", name: "Beta Workspace" },
    ];
    const onSelect = vi.fn();

    render(
      <WorkspaceSwitcher
        workspaces={workspaces}
        currentWorkspace={workspaces[0]}
        onSelectWorkspace={onSelect}
      />
    );

    expect(screen.getByText("Alpha Workspace")).toBeInTheDocument();

    const button = screen.getByRole("button", { expanded: false });
    fireEvent.click(button);

    expect(screen.getByRole("listbox")).toBeInTheDocument();
    const betaOption = screen.getByRole("option", { name: /beta workspace/i });
    fireEvent.click(betaOption);

    expect(onSelect).toHaveBeenCalledWith(workspaces[1]);
  });

  it("renders sidebar navigation links", () => {
    render(<Sidebar />);

    expect(screen.getByRole("navigation")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /projects/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /assets/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /generations/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /settings/i })).toBeInTheDocument();
  });

  it("renders top bar with credits and user initials, and toggles sign out menu", () => {
    render(
      <TopBar
        userEmail="alex@company.com"
        creditsBalance={1500}
        title="Active Projects"
      />
    );

    expect(screen.getByText("Active Projects")).toBeInTheDocument();
    expect(screen.getByTestId("credits-balance")).toHaveTextContent("1,500");
    expect(screen.getByText("A")).toBeInTheDocument();

    const userMenuButton = screen.getByRole("button", { name: /user menu/i });
    fireEvent.click(userMenuButton);

    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByText("alex@company.com")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
  });

  it("shows a placeholder while the credit balance is loading", () => {
    render(<TopBar userEmail="alex@company.com" isCreditsLoading />);

    expect(screen.getByTestId("credits-balance")).toHaveTextContent("—");
  });

  it("renders AppShell wrapping page content", async () => {
    await act(async () => {
      render(
        <AppShell
          userEmail="user@example.com"
          initialWorkspace={{ id: "ws-1", name: "Alpha Workspace" }}
        >
          <div data-testid="test-content">Dashboard Content</div>
        </AppShell>
      );
    });

    expect(screen.getByTestId("test-content")).toHaveTextContent("Dashboard Content");
  });
});
