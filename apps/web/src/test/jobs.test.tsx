import { describe, it, expect, beforeAll, afterAll, afterEach, beforeEach, vi } from "vitest";
import { act, render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { JobHistory } from "@/components/jobs/job-history";

const BASE_URL = "http://localhost:8000";
const PROJECT_ID = "proj-123";

const realtime = vi.hoisted(() => ({
  subscribeCallback: null as null | ((status: string) => void),
  updateHandler: null as null | ((payload: any) => void),
  subscriptionCount: 0,
  removedChannels: [] as unknown[],
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: "test-token" } },
      }),
    },
    channel: () => {
      realtime.subscriptionCount += 1;
      const channel = {
        on: (_type: string, _filter: unknown, handler: (payload: any) => void) => {
          realtime.updateHandler = handler;
          return channel;
        },
        subscribe: (callback: (status: string) => void) => {
          realtime.subscribeCallback = callback;
          return channel;
        },
      };
      return channel;
    },
    removeChannel: (channel: unknown) => {
      realtime.removedChannels.push(channel);
      return Promise.resolve("ok");
    },
  }),
}));

function makeJob(overrides: Record<string, unknown> = {}) {
  return {
    id: "job-1",
    project_id: PROJECT_ID,
    workspace_id: "ws-1",
    status: "queued",
    task_type: "text_to_image",
    prompt: "A red fox in snow",
    params: { aspect_ratio: "1:1" },
    error_code: null,
    error_message: null,
    queued_at: new Date().toISOString(),
    started_at: null,
    completed_at: null,
    outputs: [],
    links: { self: "/v1/generations/job-1" },
    ...overrides,
  };
}

const IMAGE_OUTPUT = {
  asset_id: "asset-out",
  kind: "image",
  mime_type: "image/png",
  signed_url: "https://storage.example.com/out.png",
  thumbnail_url: null,
};

let jobs: any[] = [];
let detailJob: any = null;
let detailCalls = 0;
let cancelCalls = 0;
let retryCalls = 0;

const server = setupServer(
  http.get(`${BASE_URL}/v1/projects/:project_id/generations`, ({ request }) => {
    const url = new URL(request.url);
    const status = url.searchParams.get("status");
    const items = status ? jobs.filter((job) => job.status === status) : jobs;
    return HttpResponse.json({ items, next_cursor: null });
  }),

  http.get(`${BASE_URL}/v1/generations/:job_id`, ({ params }) => {
    detailCalls += 1;
    const job = detailJob ?? jobs.find((item) => item.id === params.job_id);
    if (!job) return new HttpResponse(null, { status: 404 });
    return HttpResponse.json(job);
  }),

  http.post(`${BASE_URL}/v1/generations/:job_id/cancel`, ({ params }) => {
    cancelCalls += 1;
    jobs = jobs.map((job) =>
      job.id === params.job_id
        ? { ...job, status: "canceled", completed_at: new Date().toISOString() }
        : job
    );
    return HttpResponse.json(jobs.find((job) => job.id === params.job_id));
  }),

  http.post(`${BASE_URL}/v1/generations/:job_id/retry`, ({ params }) => {
    retryCalls += 1;
    const retried = makeJob({
      id: "job-2",
      parent_job_id: params.job_id,
      prompt: "Retried prompt",
    });
    jobs = [retried, ...jobs];
    return HttpResponse.json(retried, { status: 202 });
  })
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
beforeEach(() => {
  jobs = [];
  detailJob = null;
  detailCalls = 0;
  cancelCalls = 0;
  retryCalls = 0;
  realtime.subscribeCallback = null;
  realtime.updateHandler = null;
  realtime.subscriptionCount = 0;
  realtime.removedChannels = [];
});
afterEach(() => {
  server.resetHandlers();
});
afterAll(() => server.close());

function renderHistory(props: Partial<React.ComponentProps<typeof JobHistory>> = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <JobHistory projectId={PROJECT_ID} {...props} />
    </QueryClientProvider>
  );
}

function jobCard(jobId: string) {
  return screen.findByRole("article", { name: `Generation ${jobId}` });
}

describe("JobHistory & JobCard", () => {
  it("renders live status updates from Realtime and loads outputs on success", async () => {
    jobs = [makeJob()];
    renderHistory({ onUseAsInput: vi.fn() });

    const card = await jobCard("job-1");
    expect(within(card).getByText("queued")).toBeInTheDocument();

    act(() => realtime.subscribeCallback?.("SUBSCRIBED"));

    jobs = [makeJob({ status: "running", started_at: new Date().toISOString() })];
    act(() =>
      realtime.updateHandler?.({
        new: {
          id: "job-1",
          status: "running",
          error_code: null,
          error_message: null,
          started_at: jobs[0].started_at,
          completed_at: null,
        },
      })
    );

    await waitFor(() => expect(within(card).getByText("running")).toBeInTheDocument());

    jobs = [
      makeJob({
        status: "succeeded",
        started_at: jobs[0].started_at,
        completed_at: new Date().toISOString(),
        outputs: [IMAGE_OUTPUT],
      }),
    ];
    act(() =>
      realtime.updateHandler?.({
        new: {
          id: "job-1",
          status: "succeeded",
          error_code: null,
          error_message: null,
          started_at: jobs[0].started_at,
          completed_at: jobs[0].completed_at,
        },
      })
    );

    await waitFor(() => expect(within(card).getByText("succeeded")).toBeInTheDocument());
    expect(await screen.findByAltText("A red fox in snow")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /use as input/i })).toBeInTheDocument();
    expect(detailCalls).toBe(0);
  });

  it("falls back to polling when Realtime never subscribes", async () => {
    jobs = [makeJob({ status: "running", started_at: new Date().toISOString() })];
    detailJob = {
      ...jobs[0],
      status: "succeeded",
      completed_at: new Date().toISOString(),
      outputs: [IMAGE_OUTPUT],
    };

    renderHistory({ realtimeTimeoutMs: 30 });

    expect(await screen.findByText("Polling")).toBeInTheDocument();

    const card = await jobCard("job-1");
    await waitFor(() => expect(detailCalls).toBeGreaterThan(0), { timeout: 4000 });
    await waitFor(() => expect(within(card).getByText("succeeded")).toBeInTheDocument(), {
      timeout: 4000,
    });
    expect(await screen.findByAltText("A red fox in snow")).toBeInTheDocument();
  });

  it("removes its Realtime channel on unmount and never duplicates subscriptions", async () => {
    jobs = [makeJob()];

    const first = renderHistory();
    await jobCard("job-1");
    expect(realtime.subscriptionCount).toBe(1);

    // Changing filters must not re-subscribe.
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "failed" } });
    await waitFor(() => expect(realtime.subscriptionCount).toBe(1));

    first.unmount();
    await waitFor(() => expect(realtime.removedChannels).toHaveLength(1));

    renderHistory();
    await jobCard("job-1");
    expect(realtime.subscriptionCount).toBe(2);
    expect(realtime.removedChannels).toHaveLength(1);
  });

  it("cancels an active job and reflects the new status", async () => {
    jobs = [makeJob({ status: "running", started_at: new Date().toISOString() })];
    renderHistory();

    const card = await jobCard("job-1");
    fireEvent.click(within(card).getByRole("button", { name: /cancel/i }));

    await waitFor(() => expect(cancelCalls).toBe(1));
    await waitFor(() => expect(within(card).getByText("canceled")).toBeInTheDocument());
  });

  it("retries a failed job and lists the new job", async () => {
    jobs = [
      makeJob({
        status: "failed",
        error_code: "PROVIDER_ERROR",
        error_message: "Provider rejected the prompt",
      }),
    ];
    renderHistory();

    const card = await jobCard("job-1");
    expect(within(card).getByText(/provider rejected/i)).toBeInTheDocument();

    fireEvent.click(within(card).getByRole("button", { name: /retry/i }));

    await waitFor(() => expect(retryCalls).toBe(1));
    const retried = await jobCard("job-2");
    expect(within(retried).getByText("queued")).toBeInTheDocument();
  });

  it("offers generated images as composer inputs", async () => {
    jobs = [
      makeJob({
        status: "succeeded",
        completed_at: new Date().toISOString(),
        outputs: [IMAGE_OUTPUT],
      }),
    ];
    const onUseAsInput = vi.fn();

    renderHistory({ onUseAsInput });
    await jobCard("job-1");

    fireEvent.click(await screen.findByRole("button", { name: /use as input/i }));

    expect(onUseAsInput).toHaveBeenCalledTimes(1);
    expect(onUseAsInput.mock.calls[0][0]).toMatchObject({
      id: "asset-out",
      kind: "image",
      signed_url: "https://storage.example.com/out.png",
    });
  });
});
