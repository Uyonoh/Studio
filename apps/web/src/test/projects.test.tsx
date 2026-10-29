import { describe, it, expect, beforeAll, afterAll, afterEach, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ProjectsPage from "@/app/(app)/projects/page";
import { WorkspaceProvider } from "@/components/providers/workspace-context";

const mockWorkspace = {
  id: "ws-test-123",
  name: "Creative Lab",
};

let projectsData: any[] = [];

const BASE_URL = "http://localhost:8000";

const server = setupServer(
  http.get(`${BASE_URL}/v1/workspaces`, () => {
    return HttpResponse.json({
      workspaces: [mockWorkspace],
    });
  }),

  http.get(`${BASE_URL}/v1/workspaces/:workspace_id/projects`, () => {
    return HttpResponse.json({
      items: projectsData,
      next_cursor: null,
    });
  }),

  http.post(`${BASE_URL}/v1/workspaces/:workspace_id/projects`, async ({ request }) => {
    const body = (await request.json()) as { name: string; description?: string };
    const newProject = {
      id: `proj-${Date.now()}`,
      workspace_id: "ws-test-123",
      name: body.name,
      description: body.description || null,
      cover_asset_id: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      archived_at: null,
    };
    projectsData.unshift(newProject);
    return HttpResponse.json(newProject, { status: 201 });
  }),

  http.patch(`${BASE_URL}/v1/projects/:project_id`, async ({ params, request }) => {
    const { project_id } = params;
    const body = (await request.json()) as { name?: string; description?: string };
    const idx = projectsData.findIndex((p) => p.id === project_id);
    if (idx !== -1) {
      projectsData[idx] = {
        ...projectsData[idx],
        name: body.name || projectsData[idx].name,
        description: body.description ?? projectsData[idx].description,
        updated_at: new Date().toISOString(),
      };
      return HttpResponse.json(projectsData[idx]);
    }
    return new HttpResponse(null, { status: 404 });
  }),

  http.delete(`${BASE_URL}/v1/projects/:project_id`, ({ params }) => {
    const { project_id } = params;
    projectsData = projectsData.filter((p) => p.id !== project_id);
    return HttpResponse.json({ id: project_id, status: "archived" });
  })
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
beforeEach(() => {
  projectsData = [
    {
      id: "proj-1",
      workspace_id: "ws-test-123",
      name: "Cyberpunk Teaser",
      description: "Visual exploration for futuristic teaser",
      cover_asset_id: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      archived_at: null,
    },
    {
      id: "proj-2",
      workspace_id: "ws-test-123",
      name: "Architectural Stills",
      description: "Renderings of minimalist houses",
      cover_asset_id: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      archived_at: null,
    },
  ];
});
afterEach(() => {
  server.resetHandlers();
});
afterAll(() => server.close());

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: "test-token" } },
      }),
    },
  }),
}));

function renderProjectsPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <WorkspaceProvider initialWorkspace={mockWorkspace}>
        <ProjectsPage />
      </WorkspaceProvider>
    </QueryClientProvider>
  );
}

describe("ProjectsPage component with MSW", () => {
  it("renders list of projects returned by MSW", async () => {
    renderProjectsPage();

    expect(await screen.findByText("Cyberpunk Teaser", {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.getByText("Architectural Stills")).toBeInTheDocument();
    expect(screen.getByText(/2 active/i)).toBeInTheDocument();
  });

  it("filters projects in real time by search query", async () => {
    renderProjectsPage();

    expect(await screen.findByText("Cyberpunk Teaser", {}, { timeout: 4000 })).toBeInTheDocument();
    const searchInput = screen.getByPlaceholderText(/filter projects/i);

    fireEvent.change(searchInput, { target: { value: "Minimalist" } });

    expect(screen.getByText("Architectural Stills")).toBeInTheDocument();
    expect(screen.queryByText("Cyberpunk Teaser")).not.toBeInTheDocument();
  });

  it("renders empty state when no projects exist and allows opening dialog", async () => {
    server.use(
      http.get(`${BASE_URL}/v1/workspaces/:workspace_id/projects`, () => {
        return HttpResponse.json({ items: [], next_cursor: null });
      })
    );

    renderProjectsPage();

    expect(
      await screen.findByText(/your creative workspace is ready/i, {}, { timeout: 4000 })
    ).toBeInTheDocument();

    const createBtn = screen.getByRole("button", {
      name: /create your first project/i,
    });
    fireEvent.click(createBtn);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Create New Project")).toBeInTheDocument();
  });

  it("renders error state when API fails and retries on click", async () => {
    let callCount = 0;
    server.use(
      http.get(`${BASE_URL}/v1/workspaces/:workspace_id/projects`, () => {
        callCount++;
        if (callCount === 1) {
          return new HttpResponse(JSON.stringify({ detail: "Database connection failed" }), {
            status: 500,
            headers: { "Content-Type": "application/json" },
          });
        }
        return HttpResponse.json({ items: projectsData, next_cursor: null });
      })
    );

    renderProjectsPage();

    expect(
      await screen.findByRole("alert", {}, { timeout: 4000 })
    ).toHaveTextContent("Database connection failed");

    const retryBtn = screen.getByRole("button", { name: /try again/i });
    fireEvent.click(retryBtn);

    expect(await screen.findByText("Cyberpunk Teaser", {}, { timeout: 4000 })).toBeInTheDocument();
  });

  it("optimistically creates a project via dialog and closes dialog", async () => {
    renderProjectsPage();

    await screen.findByText("Cyberpunk Teaser", {}, { timeout: 4000 });

    const newBtn = screen.getByRole("button", { name: /new project/i });
    fireEvent.click(newBtn);

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();

    const nameInput = screen.getByLabelText(/project name/i);
    const descInput = screen.getByLabelText(/description/i);

    fireEvent.change(nameInput, { target: { value: "Neon Runway 2026" } });
    fireEvent.change(descInput, { target: { value: "Fashion showcase" } });

    const submitBtn = screen.getByRole("button", { name: /create project/i });
    fireEvent.click(submitBtn);

    // Dialog should close after submission
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    // The newly created project should be rendered
    expect(await screen.findByText("Neon Runway 2026", {}, { timeout: 4000 })).toBeInTheDocument();
  });

  it("closes dialog on Escape key", async () => {
    renderProjectsPage();

    await screen.findByText("Cyberpunk Teaser", {}, { timeout: 4000 });

    const newBtn = screen.getByRole("button", { name: /new project/i });
    fireEvent.click(newBtn);

    expect(screen.getByRole("dialog")).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });
});
