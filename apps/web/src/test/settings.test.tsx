import { describe, it, expect, beforeAll, afterAll, afterEach, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SettingsPage from "@/app/(app)/settings/page";
import { WorkspaceProvider } from "@/components/providers/workspace-context";

const navigation = vi.hoisted(() => ({
  tab: null as string | null,
  replace: vi.fn(),
  push: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(navigation.tab ? { tab: navigation.tab } : {}),
  useRouter: () => ({ replace: navigation.replace, push: navigation.push }),
}));

const BASE_URL = "http://localhost:8000";

let lastPatchedName: string | null = null;

const mockWorkspace = {
  id: "ws-settings-1",
  name: "Alpha Workspace",
  owner_id: "user-1",
};

const server = setupServer(
  http.get(`${BASE_URL}/v1/workspaces/:workspace_id/credits`, () => {
    return HttpResponse.json({ workspace_id: mockWorkspace.id, balance: "142.50" });
  }),
  http.get(`${BASE_URL}/v1/workspaces/:workspace_id/credits/transactions`, () => {
    return HttpResponse.json({
      items: [
        {
          id: 3,
          workspace_id: mockWorkspace.id,
          job_id: "job-12345678",
          delta: "-4.00",
          reason: "reserve",
          created_at: new Date("2026-11-01T10:15:00Z").toISOString(),
          balance_after: "142.50",
          model_name: "Flux 1.1 Pro",
          job_status: "succeeded",
          prompt: "A neon cityscape",
        },
      ],
      next_before_id: null,
      summary: {
        window_days: 30,
        spent: "4.00",
        refunded: "0.00",
        granted: "500.00",
        transactions: 1,
      },
    });
  }),
  http.get(`${BASE_URL}/v1/models`, () => {
    return HttpResponse.json([
      {
        id: "model-1",
        slug: "flux-1-1-pro",
        display_name: "Flux 1.1 Pro",
        task_type: "text_to_image",
        provider_id: "replicate",
        input_schema: {},
        default_params: {},
        cost_credits: "12.00",
        required_input_roles: [],
      },
    ]);
  }),
  http.patch(`${BASE_URL}/v1/workspaces/:workspace_id`, async ({ params, request }) => {
    const body = (await request.json()) as { name: string };
    lastPatchedName = body.name;
    return HttpResponse.json({
      id: params.workspace_id,
      name: body.name,
      owner_id: mockWorkspace.owner_id,
    });
  })
);

function renderSettings() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <WorkspaceProvider initialWorkspace={mockWorkspace}>
        <SettingsPage />
      </WorkspaceProvider>
    </QueryClientProvider>
  );
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  navigation.tab = null;
  navigation.replace.mockClear();
  navigation.push.mockClear();
  lastPatchedName = null;
});
afterAll(() => server.close());

beforeEach(() => {
  navigation.tab = null;
});

describe("Settings page", () => {
  it("opens the usage section by default with live balance and ledger activity", async () => {
    renderSettings();

    await waitFor(() => {
      expect(screen.getByTestId("usage-balance")).toHaveTextContent("142.5");
    });
    expect(await screen.findByText(/Flux 1\.1 Pro/)).toBeInTheDocument();
    expect(screen.getByText("A neon cityscape")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /usage & billing/i })).toHaveAttribute(
      "aria-selected",
      "true"
    );
  });

  it("switches tabs through the URL", () => {
    renderSettings();

    fireEvent.click(screen.getByRole("tab", { name: /general/i }));

    expect(navigation.replace).toHaveBeenCalledWith("/settings?tab=general", { scroll: false });
  });

  it("renames the workspace from the general section", async () => {
    navigation.tab = "general";
    renderSettings();

    const input = await screen.findByLabelText(/workspace name/i);
    expect(input).toHaveValue("Alpha Workspace");

    fireEvent.change(input, { target: { value: "Beta Lab" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(lastPatchedName).toBe("Beta Lab");
    });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
    });
  });

  it("lists enabled models with their credit cost", async () => {
    navigation.tab = "models";
    renderSettings();

    expect(await screen.findByText("Flux 1.1 Pro")).toBeInTheDocument();
    expect(screen.getByText("12 credits")).toBeInTheDocument();
    expect(screen.getByText("Replicate")).toBeInTheDocument();
  });
});
