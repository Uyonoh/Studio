import { describe, it, expect, beforeAll, afterAll, afterEach, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { GenerationComposer, deriveTaskType } from "@/components/composer/generation-composer";

const BASE_URL = "http://localhost:8000";
const PROJECT_ID = "proj-123";

interface CapturedRequest {
  body: any;
  idempotencyKey: string | null;
}

let captured: CapturedRequest[] = [];
let postDelay = 0;
let postResponder: ((body: any) => Response) | null = null;

const IMAGE_ASSET = {
  id: "asset-input",
  workspace_id: "ws-1",
  project_id: PROJECT_ID,
  kind: "image",
  origin: "upload",
  mime_type: "image/png",
  size_bytes: 1024,
  width: 512,
  height: 512,
  duration_ms: null,
  fps: null,
  storage_path: "uploads/input.png",
  thumbnail_path: null,
  thumbnail_url: null,
  signed_url: "https://storage.example.com/input.png",
  source_job_id: null,
  parent_asset_id: null,
  metadata: { filename: "input.png" },
  created_at: new Date().toISOString(),
};

const SECOND_IMAGE_ASSET = {
  ...IMAGE_ASSET,
  id: "asset-input-2",
  storage_path: "uploads/second.png",
  signed_url: "https://storage.example.com/second.png",
  metadata: { filename: "second.png" },
};

const MODELS = [
  {
    id: "m1",
    slug: "img-fast",
    display_name: "Fast Image",
    task_type: "text_to_image",
    provider_id: "fake",
    input_schema: {
      type: "object",
      properties: {
        aspect_ratio: { type: "string", enum: ["1:1", "16:9"], default: "1:1" },
        seed: { type: "integer", minimum: 0, maximum: 100 },
      },
      additionalProperties: false,
    },
    default_params: { aspect_ratio: "1:1" },
    cost_credits: "1.00",
    required_input_roles: [],
  },
  {
    id: "m1-fal",
    slug: "img-pro",
    display_name: "Pro Image",
    task_type: "text_to_image",
    provider_id: "fal",
    input_schema: {
      type: "object",
      properties: {
        aspect_ratio: { type: "string", enum: ["1:1", "16:9"], default: "1:1" },
        seed: { type: "integer", minimum: 0, maximum: 100 },
      },
      additionalProperties: false,
    },
    default_params: { aspect_ratio: "1:1" },
    cost_credits: "5.00",
    required_input_roles: [],
  },
  {
    id: "m2",
    slug: "img-remix",
    display_name: "Image Remix",
    task_type: "image_to_image",
    provider_id: "fake",
    input_schema: {
      type: "object",
      properties: {
        strength: { type: "number", minimum: 0, maximum: 1, default: 0.75 },
      },
      additionalProperties: false,
    },
    default_params: { strength: 0.75 },
    cost_credits: "1.50",
    required_input_roles: ["init_image"],
    input_capabilities: [
      {
        role: "init_image",
        kind: "image",
        required: true,
        max_count: 3,
        label: "Source images",
      },
    ],
  },
  {
    id: "m3",
    slug: "vid-fast",
    display_name: "Fast Video",
    task_type: "text_to_video",
    provider_id: "fake",
    input_schema: {
      type: "object",
      properties: {
        duration_s: { type: "integer", enum: [3, 5], default: 5 },
      },
      additionalProperties: false,
    },
    default_params: { duration_s: 5 },
    cost_credits: "5.00",
    required_input_roles: [],
  },
  {
    id: "m4",
    slug: "vid-anim",
    display_name: "Animate Image",
    task_type: "image_to_video",
    provider_id: "fake",
    input_schema: {
      type: "object",
      properties: {
        duration_s: { type: "integer", enum: [3, 5], default: 5 },
      },
      additionalProperties: false,
    },
    default_params: { duration_s: 5 },
    cost_credits: "7.50",
    required_input_roles: ["first_frame"],
  },
  {
    id: "m5",
    slug: "vid-frames",
    display_name: "Animate First/Last Frame",
    task_type: "image_to_video",
    provider_id: "fal",
    input_schema: {
      type: "object",
      properties: {
        duration_s: { type: "integer", enum: [3, 5], default: 5 },
      },
      additionalProperties: false,
    },
    default_params: { duration_s: 5 },
    cost_credits: "9.00",
    required_input_roles: ["first_frame"],
    input_capabilities: [
      {
        role: "first_frame",
        kind: "image",
        required: true,
        max_count: 1,
        label: "First frame",
      },
      {
        role: "last_frame",
        kind: "image",
        required: false,
        max_count: 1,
        label: "Last frame",
      },
    ],
  },
];

const server = setupServer(
  http.get(`${BASE_URL}/v1/models`, ({ request }) => {
    const url = new URL(request.url);
    const taskType = url.searchParams.get("task_type");
    const models = taskType ? MODELS.filter((model) => model.task_type === taskType) : MODELS;
    return HttpResponse.json(models);
  }),

  http.get(`${BASE_URL}/v1/projects/:project_id/assets`, () => {
    return HttpResponse.json({ items: [IMAGE_ASSET, SECOND_IMAGE_ASSET], next_cursor: null });
  }),

  http.post(`${BASE_URL}/v1/projects/:project_id/generations`, async ({ request }) => {
    const body = (await request.json()) as any;
    captured.push({
      body,
      idempotencyKey: request.headers.get("Idempotency-Key"),
    });

    if (postDelay > 0) {
      await new Promise((resolve) => setTimeout(resolve, postDelay));
    }

    if (postResponder) {
      return postResponder(body);
    }

    return HttpResponse.json(
      {
        id: `job-${captured.length}`,
        project_id: PROJECT_ID,
        workspace_id: "ws-1",
        status: "queued",
        task_type: body.task_type,
        prompt: body.prompt,
        params: body.params,
        error_code: null,
        error_message: null,
        queued_at: new Date().toISOString(),
        started_at: null,
        completed_at: null,
        outputs: [],
        links: { self: "/v1/generations/job-1" },
      },
      { status: 202 }
    );
  })
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
beforeEach(() => {
  captured = [];
  postDelay = 0;
  postResponder = null;
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

function renderComposer() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <GenerationComposer projectId={PROJECT_ID} />
    </QueryClientProvider>
  );
}

function clickSegment(groupName: string, buttonName: RegExp | string) {
  const group = screen.getByRole("group", { name: groupName });
  fireEvent.click(within(group).getByRole("button", { name: buttonName }));
}

async function waitForModel(slug: string) {
  const trigger = await screen.findByTestId("model-picker-trigger");
  await waitFor(() => expect(trigger).toHaveAttribute("data-value", slug));
}

function setPrompt(value: string) {
  fireEvent.change(screen.getByRole("textbox", { name: /^prompt$/i }), {
    target: { value },
  });
}

function submit() {
  fireEvent.click(screen.getByRole("button", { name: /^generate$/i }));
}

async function selectInputImage() {
  const assetButton = await screen.findByRole("button", { name: "Use input.png" });
  fireEvent.click(assetButton);
}

describe("GenerationComposer", () => {
  it("derives the task type from mode and image input", () => {
    expect(deriveTaskType("image", false)).toBe("text_to_image");
    expect(deriveTaskType("image", true)).toBe("image_to_image");
    expect(deriveTaskType("video", false)).toBe("text_to_video");
    expect(deriveTaskType("video", true)).toBe("image_to_video");
  });

  it("submits a text-to-image request with schema defaults", async () => {
    renderComposer();
    await waitForModel("img-fast");

    setPrompt("A red fox in fresh snow");
    submit();

    await waitFor(() => expect(captured).toHaveLength(1));
    expect(captured[0].body).toEqual({
      model: "img-fast",
      task_type: "text_to_image",
      prompt: "A red fox in fresh snow",
      inputs: [],
      params: { aspect_ratio: "1:1" },
    });
    expect(captured[0].idempotencyKey).toBeTruthy();
    expect(await screen.findByRole("status")).toHaveTextContent(/queued/i);
  });

  it("submits image+text → image with an init_image input", async () => {
    renderComposer();
    await waitForModel("img-fast");

    clickSegment("Starting point", /text \+ image/i);
    await waitForModel("img-remix");

    await selectInputImage();
    setPrompt("Turn this into a watercolor painting");
    submit();

    await waitFor(() => expect(captured).toHaveLength(1));
    expect(captured[0].body).toMatchObject({
      model: "img-remix",
      task_type: "image_to_image",
      prompt: "Turn this into a watercolor painting",
      inputs: [{ asset_id: "asset-input", role: "init_image" }],
      params: { strength: 0.75 },
    });
  });

  it("submits a text-to-video request", async () => {
    renderComposer();
    await waitForModel("img-fast");

    clickSegment("Output type", /video/i);
    await waitForModel("vid-fast");

    setPrompt("Slow dolly-in over a misty forest");
    submit();

    await waitFor(() => expect(captured).toHaveLength(1));
    expect(captured[0].body).toEqual({
      model: "vid-fast",
      task_type: "text_to_video",
      prompt: "Slow dolly-in over a misty forest",
      inputs: [],
      params: { duration_s: 5 },
    });
  });

  it("submits image+text → video with a first_frame input", async () => {
    renderComposer();
    await waitForModel("img-fast");

    clickSegment("Output type", /video/i);
    clickSegment("Starting point", /text \+ image/i);
    await waitForModel("vid-anim");

    await selectInputImage();
    setPrompt("Gentle camera push, golden hour, film grain");
    submit();

    await waitFor(() => expect(captured).toHaveLength(1));
    expect(captured[0].body).toMatchObject({
      model: "vid-anim",
      task_type: "image_to_video",
      prompt: "Gentle camera push, golden hour, film grain",
      inputs: [{ asset_id: "asset-input", role: "first_frame" }],
      params: { duration_s: 5 },
    });
  });

  it("submits multiple source images when the model supports them", async () => {
    renderComposer();
    await waitForModel("img-fast");

    clickSegment("Starting point", /text \+ image/i);
    await waitForModel("img-remix");

    await selectInputImage();
    const sourceImages = screen.getByRole("group", { name: /source images/i });
    fireEvent.click(within(sourceImages).getByRole("button", { name: "Use second.png" }));
    setPrompt("Blend these two references into one scene");
    submit();

    await waitFor(() => expect(captured).toHaveLength(1));
    expect(captured[0].body).toMatchObject({
      model: "img-remix",
      task_type: "image_to_image",
      inputs: [
        { asset_id: "asset-input", role: "init_image" },
        { asset_id: "asset-input-2", role: "init_image" },
      ],
    });
  });

  it("submits first and last frames when the model supports them", async () => {
    renderComposer();
    await waitForModel("img-fast");

    clickSegment("Output type", /video/i);
    clickSegment("Starting point", /text \+ image/i);
    await waitForModel("vid-anim");

    fireEvent.click(screen.getByTestId("model-picker-trigger"));
    fireEvent.click(screen.getByRole("option", { name: /animate first\/last frame/i }));
    await waitForModel("vid-frames");

    const firstFrame = screen.getByRole("group", { name: /^first frame$/i });
    const lastFrame = screen.getByRole("group", { name: /^last frame$/i });
    fireEvent.click(within(firstFrame).getByRole("button", { name: "Use input.png" }));
    fireEvent.click(within(lastFrame).getByRole("button", { name: "Use second.png" }));

    setPrompt("Morph between the two frames");
    submit();

    await waitFor(() => expect(captured).toHaveLength(1));
    expect(captured[0].body).toMatchObject({
      model: "vid-frames",
      task_type: "image_to_video",
      inputs: [
        { asset_id: "asset-input", role: "first_frame" },
        { asset_id: "asset-input-2", role: "last_frame" },
      ],
    });
  });

  it("blocks image flows until a source image is selected", async () => {
    renderComposer();
    await waitForModel("img-fast");

    clickSegment("Starting point", /text \+ image/i);
    await waitForModel("img-remix");

    submit();

    expect(await screen.findByText(/choose a source image/i)).toBeInTheDocument();
    expect(captured).toHaveLength(0);
  });

  it("does not create a second job on double click", async () => {
    postDelay = 50;
    renderComposer();
    await waitForModel("img-fast");

    setPrompt("Double click guard");
    const button = screen.getByRole("button", { name: /^generate$/i });
    fireEvent.click(button);
    fireEvent.click(button);

    await waitFor(() => expect(captured).toHaveLength(1));
    await new Promise((resolve) => setTimeout(resolve, 120));
    expect(captured).toHaveLength(1);
  });

  it("maps schema validation errors to the offending field", async () => {
    renderComposer();
    await waitForModel("img-fast");

    const seedInput = screen.getByLabelText(/seed/i);
    fireEvent.change(seedInput, { target: { value: "500" } });

    submit();

    expect(await screen.findByText(/must be at most 100/i)).toBeInTheDocument();
    expect(seedInput).toHaveAttribute("aria-invalid", "true");
    expect(captured).toHaveLength(0);
  });

  it("groups models by provider and changes the selection from the picker", async () => {
    renderComposer();
    await waitForModel("img-fast");

    fireEvent.click(screen.getByTestId("model-picker-trigger"));

    expect(await screen.findByTestId("model-provider-fake")).toHaveTextContent(
      /deterministic test provider/i
    );
    expect(screen.getByTestId("model-provider-fal")).toHaveTextContent(/fal\.ai/i);

    fireEvent.click(screen.getByRole("option", { name: /pro image/i }));

    await waitForModel("img-pro");
    expect(screen.getByTestId("generation-cost")).toHaveTextContent("5.00");
  });

  it("closes the model picker with Escape and restores focus", async () => {
    renderComposer();
    await waitForModel("img-fast");

    const trigger = screen.getByTestId("model-picker-trigger");
    fireEvent.click(trigger);
    const listbox = screen.getByRole("listbox");
    expect(listbox).toHaveFocus();

    fireEvent.keyDown(listbox, { key: "Escape" });

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("shows the selected model's credit cost and updates it live", async () => {
    renderComposer();
    await waitForModel("img-fast");

    expect(screen.getByTestId("generation-cost")).toHaveTextContent("1.00");

    clickSegment("Output type", /video/i);
    await waitForModel("vid-fast");

    expect(screen.getByTestId("generation-cost")).toHaveTextContent("5.00");
  });

  it("surfaces a 402 insufficient-credits error", async () => {
    postResponder = () =>
      HttpResponse.json(
        {
          type: "https://studio.example.com/errors/insufficient_credits",
          title: "Insufficient Credits",
          status: 402,
          detail: "Workspace balance is too low",
          error_code: "INSUFFICIENT_CREDITS",
        },
        { status: 402, headers: { "Content-Type": "application/problem+json" } }
      );

    renderComposer();
    await waitForModel("img-fast");

    setPrompt("Costly generation");
    submit();

    expect(await screen.findByRole("alert")).toHaveTextContent(/not enough credits/i);
  });

  it("surfaces a 429 concurrency limit with the Retry-After delay", async () => {
    postResponder = () =>
      HttpResponse.json(
        {
          type: "https://studio.example.com/errors/concurrency_limit",
          title: "Concurrency Limit",
          status: 429,
          detail: "Workspace active generation limit reached",
          error_code: "CONCURRENCY_LIMIT",
        },
        {
          status: 429,
          headers: { "Content-Type": "application/problem+json", "Retry-After": "7" },
        }
      );

    renderComposer();
    await waitForModel("img-fast");

    setPrompt("Too many jobs");
    submit();

    expect(await screen.findByRole("alert")).toHaveTextContent(/retry in 7s/i);
  });

  it("reuses the idempotency key when retrying an unchanged submission", async () => {
    let attempts = 0;
    postResponder = () => {
      attempts += 1;
      if (attempts === 1) {
        return HttpResponse.json(
          {
            type: "https://studio.example.com/errors/service_unavailable",
            title: "Service Unavailable",
            status: 503,
            detail: "Queue unavailable",
            error_code: "SERVICE_UNAVAILABLE",
          },
          { status: 503, headers: { "Content-Type": "application/problem+json" } }
        );
      }
      return HttpResponse.json(
        {
          id: "job-retry",
          project_id: PROJECT_ID,
          workspace_id: "ws-1",
          status: "queued",
          task_type: "text_to_image",
          prompt: "Retry me",
          params: { aspect_ratio: "1:1" },
          error_code: null,
          error_message: null,
          queued_at: new Date().toISOString(),
          started_at: null,
          completed_at: null,
          outputs: [],
          links: { self: "/v1/generations/job-retry" },
        },
        { status: 202 }
      );
    };

    renderComposer();
    await waitForModel("img-fast");

    setPrompt("Retry me");
    submit();

    expect(await screen.findByRole("alert")).toHaveTextContent(/queue unavailable/i);

    submit();

    await waitFor(() => expect(captured).toHaveLength(2));
    expect(captured[0].idempotencyKey).toBeTruthy();
    expect(captured[1].idempotencyKey).toBe(captured[0].idempotencyKey);
  });
});

