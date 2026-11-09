import { describe, it, expect, beforeAll, afterAll, afterEach, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AssetLibrary } from "@/components/assets/asset-library";
import { AssetUploadZone } from "@/components/assets/asset-upload-zone";
import { uploadAssetWithProgress } from "@/hooks/use-assets";

const BASE_URL = "http://localhost:8000";
const mockProjectId = "proj-123";

let mockAssets: any[] = [];
let listRequestCount = 0;
let completeAttempts = 0;

const server = setupServer(
  http.get(`${BASE_URL}/v1/projects/:project_id/assets`, ({ request }) => {
    const url = new URL(request.url);
    const kind = url.searchParams.get("kind");
    const origin = url.searchParams.get("origin");
    const cursor = url.searchParams.get("cursor");
    listRequestCount += 1;

    let filtered = [...mockAssets];
    if (kind) {
      filtered = filtered.filter((a) => a.kind === kind);
    }
    if (origin) {
      filtered = filtered.filter((a) => a.origin === origin);
    }

    // Two-page fixture used by the cursor pagination test.
    if (mockAssets.length > 2 && !cursor) {
      return HttpResponse.json({ items: filtered.slice(0, 2), next_cursor: "page-2" });
    }
    if (cursor === "page-2") {
      return HttpResponse.json({ items: filtered.slice(2), next_cursor: null });
    }

    return HttpResponse.json({
      items: filtered,
      next_cursor: null,
    });
  }),

  http.get(`${BASE_URL}/v1/assets/:asset_id`, ({ params }) => {
    const { asset_id } = params;
    const asset = mockAssets.find((a) => a.id === asset_id);
    if (asset) {
      return HttpResponse.json(asset);
    }
    return new HttpResponse(JSON.stringify({ detail: "Asset not found" }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });
  }),

  http.delete(`${BASE_URL}/v1/assets/:asset_id`, ({ params }) => {
    const { asset_id } = params;
    mockAssets = mockAssets.filter((a) => a.id !== asset_id);
    return new HttpResponse(null, { status: 204 });
  }),

  http.post(`${BASE_URL}/v1/projects/:project_id/assets/uploads`, async () => {
    return HttpResponse.json(
      {
        asset_id: "asset-new-upload",
        upload_url: "https://storage.example.com/upload-signed",
      },
      { status: 201 }
    );
  }),

  http.post(`${BASE_URL}/v1/assets/:asset_id/complete`, () => {
    completeAttempts += 1;
    if (completeAttempts === 1) {
      return new HttpResponse(JSON.stringify({ detail: "Processing failed" }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      });
    }

    const newAsset = {
      id: "asset-new-upload",
      workspace_id: "ws-test",
      project_id: mockProjectId,
      kind: "image",
      origin: "upload",
      mime_type: "image/png",
      size_bytes: 1024,
      width: 512,
      height: 512,
      duration_ms: null,
      fps: null,
      storage_path: "uploads/asset-new.png",
      thumbnail_path: "uploads/asset-new-thumb.jpg",
      thumbnail_url: "https://storage.example.com/asset-new-thumb.jpg",
      signed_url: "https://storage.example.com/asset-new.png",
      source_job_id: null,
      parent_asset_id: null,
      metadata: { filename: "uploaded_photo.png" },
      created_at: new Date().toISOString(),
    };
    mockAssets.unshift(newAsset);
    return HttpResponse.json(newAsset);
  })
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
beforeEach(() => {
  listRequestCount = 0;
  completeAttempts = 0;
  mockAssets = [
    {
      id: "asset-img-1",
      workspace_id: "ws-test",
      project_id: mockProjectId,
      kind: "image",
      origin: "generated",
      mime_type: "image/png",
      size_bytes: 2048576,
      width: 1024,
      height: 1024,
      duration_ms: null,
      fps: null,
      storage_path: "generations/cyberpunk_neon.png",
      thumbnail_path: null,
      thumbnail_url: null,
      signed_url: "https://storage.example.com/cyberpunk_neon.png",
      source_job_id: "job-888",
      parent_asset_id: "asset-parent-1",
      metadata: {
        filename: "cyberpunk_neon.png",
        prompt: "Neon cyber city rain 4k octane render",
        model: "sdxl-turbo",
      },
      lineage: {
        source_job: {
          id: "job-888",
          task_type: "image_to_video",
          status: "succeeded",
          prompt: "Neon cyber city rain 4k octane render",
          negative_prompt: "blurry, low quality",
          params: { duration_s: 5, seed: 42 },
          model_slug: "sdxl-turbo",
          model_display_name: "SDXL Turbo",
          created_at: new Date().toISOString(),
        },
        inputs: [
          {
            asset_id: "asset-input-1",
            kind: "image",
            role: "first_frame",
            signed_url: "https://storage.example.com/input_frame.png",
            thumbnail_url: null,
          },
        ],
        parent: {
          asset_id: "asset-parent-1",
          kind: "image",
          role: null,
          signed_url: "https://storage.example.com/parent.png",
          thumbnail_url: null,
        },
      },
      created_at: new Date().toISOString(),
    },
    {
      id: "asset-vid-2",
      workspace_id: "ws-test",
      project_id: mockProjectId,
      kind: "video",
      origin: "upload",
      mime_type: "video/mp4",
      size_bytes: 10485760,
      width: 1920,
      height: 1080,
      duration_ms: 5000,
      fps: "30",
      storage_path: "uploads/drone_shot.mp4",
      thumbnail_path: null,
      thumbnail_url: null,
      signed_url: "https://storage.example.com/drone_shot.mp4",
      source_job_id: null,
      parent_asset_id: null,
      metadata: {
        filename: "drone_shot.mp4",
      },
      created_at: new Date().toISOString(),
    },
  ];
});
afterEach(() => {
  server.resetHandlers();
  vi.unstubAllGlobals();
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

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

function renderAssetLibrary() {
  return renderWithQueryClient(<AssetLibrary projectId={mockProjectId} />);
}

/** Minimal XHR stand-in so direct-to-storage uploads resolve in jsdom. */
function stubXmlHttpRequest() {
  class FakeXmlHttpRequest {
    upload: { onprogress: ((e: ProgressEvent) => void) | null } = { onprogress: null };
    status = 200;
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    onabort: (() => void) | null = null;

    open() {}
    setRequestHeader() {}
    send() {
      this.upload.onprogress?.({
        lengthComputable: true,
        loaded: 512,
        total: 1024,
      } as ProgressEvent);
      setTimeout(() => this.onload?.(), 0);
    }
  }

  vi.stubGlobal("XMLHttpRequest", FakeXmlHttpRequest);
}

describe("AssetLibrary & Upload Components", () => {
  it("renders asset items from MSW", async () => {
    renderAssetLibrary();

    expect(
      await screen.findByText("cyberpunk_neon.png", {}, { timeout: 4000 })
    ).toBeInTheDocument();
    expect(screen.getByText("drone_shot.mp4")).toBeInTheDocument();
  });

  it("filters assets by kind (images vs videos)", async () => {
    renderAssetLibrary();

    expect(
      await screen.findByText("cyberpunk_neon.png", {}, { timeout: 4000 })
    ).toBeInTheDocument();

    const videoFilterBtn = screen.getByRole("button", { name: /videos/i });
    fireEvent.click(videoFilterBtn);

    expect(
      await screen.findByText("drone_shot.mp4", {}, { timeout: 4000 })
    ).toBeInTheDocument();
    expect(screen.queryByText("cyberpunk_neon.png")).not.toBeInTheDocument();
  });

  it("loads the next cursor page when more assets exist", async () => {
    mockAssets = [
      ...mockAssets,
      {
        id: "asset-img-3",
        workspace_id: "ws-test",
        project_id: mockProjectId,
        kind: "image",
        origin: "upload",
        mime_type: "image/png",
        size_bytes: 2048,
        width: 800,
        height: 600,
        duration_ms: null,
        fps: null,
        storage_path: "uploads/third.png",
        thumbnail_path: null,
        thumbnail_url: null,
        signed_url: "https://storage.example.com/third.png",
        source_job_id: null,
        parent_asset_id: null,
        metadata: { filename: "third_page_asset.png" },
        created_at: new Date().toISOString(),
      },
    ];

    renderAssetLibrary();

    expect(
      await screen.findByText("cyberpunk_neon.png", {}, { timeout: 4000 })
    ).toBeInTheDocument();
    expect(screen.queryByText("third_page_asset.png")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /load more assets/i }));

    expect(
      await screen.findByText("third_page_asset.png", {}, { timeout: 4000 })
    ).toBeInTheDocument();
  });

  it("opens asset detail drawer on click and renders metadata and lineage", async () => {
    renderAssetLibrary();

    const assetItem = await screen.findByText("cyberpunk_neon.png", {}, { timeout: 4000 });
    fireEvent.click(assetItem);

    // Detail drawer opens
    expect(await screen.findByRole("dialog", {}, { timeout: 4000 })).toBeInTheDocument();
    expect(await screen.findByText(/1024/)).toBeInTheDocument();
    expect(screen.getByText(/SDXL Turbo/i)).toBeInTheDocument();
    expect(screen.getByText(/Neon cyber city rain 4k/i)).toBeInTheDocument();

    // Lineage: job, params, inputs and parent asset
    expect(screen.getByText(/image to video · succeeded/i)).toBeInTheDocument();
    expect(screen.getByText(/duration_s: 5/)).toBeInTheDocument();
    expect(screen.getByText(/blurry, low quality/i)).toBeInTheDocument();
    expect(screen.getAllByText(/first frame/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/derived from/i)).toBeInTheDocument();
  });

  it("deletes asset from drawer with confirmation", async () => {
    renderAssetLibrary();

    const assetItem = await screen.findByText("cyberpunk_neon.png", {}, { timeout: 4000 });
    fireEvent.click(assetItem);

    const deleteBtn = await screen.findByRole("button", { name: /^delete$/i });
    fireEvent.click(deleteBtn);

    // Confirmation appears
    const confirmBtn = await screen.findByRole("button", { name: /confirm delete/i });
    fireEvent.click(confirmBtn);

    // Should remove from grid
    await waitFor(() => {
      expect(screen.queryByText("cyberpunk_neon.png")).not.toBeInTheDocument();
    });
  });

  it("refetches the asset when its signed media URL fails to load", async () => {
    renderAssetLibrary();

    await screen.findByText("cyberpunk_neon.png", {}, { timeout: 4000 });
    const requestsBefore = listRequestCount;

    const image = screen.getByAltText("cyberpunk_neon.png");
    fireEvent.error(image);

    await waitFor(() => {
      expect(listRequestCount).toBeGreaterThan(requestsBefore);
    });
  });

  it("rejects uploads exceeding size limit or unsupported formats", async () => {
    const oversizedFile = new File([new ArrayBuffer(10)], "huge.png", { type: "image/png" });
    Object.defineProperty(oversizedFile, "size", { value: 250 * 1024 * 1024 });

    await expect(
      uploadAssetWithProgress({
        projectId: mockProjectId,
        file: oversizedFile,
      })
    ).rejects.toThrow(/exceeds maximum allowed size/i);

    const invalidTypeFile = new File(["dummy"], "text.pdf", { type: "application/pdf" });
    await expect(
      uploadAssetWithProgress({
        projectId: mockProjectId,
        file: invalidTypeFile,
      })
    ).rejects.toThrow(/only images.*and videos.*are allowed/i);
  });

  it("shows a retry action when an upload fails and succeeds on retry", async () => {
    stubXmlHttpRequest();
    const onUploadSuccess = vi.fn();

    const { container } = render(
      <AssetUploadZone projectId={mockProjectId} onUploadSuccess={onUploadSuccess} />
    );

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["binary"], "retry_me.png", { type: "image/png" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    // First attempt fails at the complete step
    expect(await screen.findByText("Failed", {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.getByText(/processing failed/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /retry upload retry_me.png/i }));

    // Retry issues a fresh signed URL and succeeds
    expect(await screen.findByText("Ready", {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.getByText("512×512")).toBeInTheDocument();
    expect(container.querySelector("img")?.getAttribute("src")).toContain("asset-new-thumb.jpg");
    expect(onUploadSuccess).toHaveBeenCalledTimes(1);
    expect(completeAttempts).toBe(2);
  });
});
